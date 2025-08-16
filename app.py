import os
import json
import uuid
import datetime
import threading
import base64
from io import BytesIO
import shutil
from pathlib import Path
from flask import (
    Flask, request, session, redirect, url_for, render_template,
    jsonify, abort, send_from_directory
)
import requests
import qrcode

from config import (
    GEMINI_API_KEY, BASE_DIR, GEMINI_RECOMMEND_MODEL,
    GEMINI_FAQ_MODEL, UPI_ID
)

app = Flask(__name__)
app.secret_key = "dev-secret-key"  # Replace in production

DATA_DIR = Path(BASE_DIR) / "data"
UPLOAD_DIR = Path(BASE_DIR) / "retailer_uploads"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

AUTH_FILE = DATA_DIR / "Auth.json"
COUNT_FILE = DATA_DIR / "count.json"
FAQ_FILE = DATA_DIR / "FAQ.json"
PURCHASE_FILE = DATA_DIR / "purchase.json"  # Will now store legacy 'requests' and new 'orders'

FILE_LOCK = threading.Lock()

CHAT_SESSIONS = {}

# --------------- Utility JSON I/O ---------------
def load_json(path, default):
    with FILE_LOCK:
        if not path.exists():
            path.write_text(json.dumps(default, indent=2))
            return default
        try:
            return json.loads(path.read_text() or "null") or default
        except json.JSONDecodeError:
            return default

def save_json(path, data):
    with FILE_LOCK:
        path.write_text(json.dumps(data, indent=2))

def now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def ensure_files():
    load_json(AUTH_FILE, {"accounts": {}})
    load_json(COUNT_FILE, {
        "recommendation_ratings": {"excellent": 0, "good": 0, "bad": 0},
        "last_updated": now_iso()
    })
    load_json(FAQ_FILE, {
        "static_faq": [
            {"q": "How do I register?", "a": "Use Register and choose a role."},
            {"q": "How do I upload a product?", "a": "Retailers upload from the store panel."},
            {"q": "How does AI recommend items?", "a": "It matches your stated preferences to item metadata."},
            {"q": "How do I request a purchase?", "a": "Open a product and click Buy Now."},
            {"q": "Can I rate recommendations?", "a": "Yes, via the popup after each recommendation response."}
        ],
        "dynamic_log": []
    })
    # purchase.json: keep backward compatibility with earlier "requests" and add "orders"
    existing = load_json(PURCHASE_FILE, {})
    if "requests" not in existing:
        existing["requests"] = []
    if "orders" not in existing:
        existing["orders"] = []
    save_json(PURCHASE_FILE, existing)

ensure_files()
@app.context_processor
def inject_cart_count():
    if session.get("role") == "user":
        return {"cart_count": len(session.get("cart", []))}
    return {"cart_count": 0}
# --------------- Auth Utilities ---------------
def get_account(username):
    auth = load_json(AUTH_FILE, {"accounts": {}})
    return auth["accounts"].get(username)

def add_account(username, password, role):
    auth = load_json(AUTH_FILE, {"accounts": {}})
    if username in auth["accounts"]:
        return False, "Username already exists."
    auth["accounts"][username] = {
        "username": username,
        "role": role,
        "password": password,
        "created_at": now_iso(),
        "last_login": None,
        "profile": {}
    }
    save_json(AUTH_FILE, auth)
    return True, "Registered."

def update_last_login(username):
    auth = load_json(AUTH_FILE, {"accounts": {}})
    if username in auth["accounts"]:
        auth["accounts"][username]["last_login"] = now_iso()
        save_json(AUTH_FILE, auth)

# --------------- Inventory / Items ---------------
def iter_all_items():
    if not UPLOAD_DIR.exists():
        return
    for retailer_dir in UPLOAD_DIR.iterdir():
        if not retailer_dir.is_dir():
            continue
        for item_dir in retailer_dir.iterdir():
            if not item_dir.is_dir():
                continue
            details_file = item_dir / "details.json"
            if details_file.exists():
                try:
                    data = json.loads(details_file.read_text())
                    yield data
                except Exception:
                    continue

def get_item(retailer, item_id):
    details = UPLOAD_DIR / retailer / item_id / "details.json"
    if details.exists():
        try:
            return json.loads(details.read_text())
        except:
            return None
    return None

def save_item(retailer, item_data, image_file):
    item_id = str(uuid.uuid4())
    item_folder = UPLOAD_DIR / retailer / item_id
    item_folder.mkdir(parents=True, exist_ok=True)
    ext = ""
    if image_file and "." in image_file.filename:
        ext = image_file.filename.rsplit(".", 1)[1].lower()
    image_name = f"{item_id}.{ext}" if ext else f"{item_id}.img"
    if image_file:
        image_path = item_folder / image_name
        image_file.save(str(image_path))
    full_desc = item_data.get("description", "").strip()
    short = (full_desc[:120] + "...") if len(full_desc) > 120 else full_desc
    details = {
        "item_id": item_id,
        "retailer": retailer,
        "name": item_data.get("name", "").strip(),
        "category": item_data.get("category", "other"),
        "description_full": full_desc,
        "description_short": short,
        "image_filename": image_name,
        "price": float(item_data.get("price") or 0),
        "stock": int(item_data.get("stock") or 0),
        "tags": [t.strip() for t in item_data.get("tags", "").split(",") if t.strip()],
        "created_at": now_iso(),
        "updated_at": now_iso()
    }
    save_json(item_folder / "details.json", details)
    return details

def retailer_item_path(retailer_username, item_id):
    return UPLOAD_DIR / retailer_username / item_id

def update_item(retailer_username, item_id, fields: dict):
    folder = retailer_item_path(retailer_username, item_id)
    details_file = folder / "details.json"
    if not details_file.exists():
        return None
    try:
        details = json.loads(details_file.read_text())
    except:
        return None
    changed = False
    def set_if(key, cast=None):
        nonlocal changed
        if key in fields and fields[key] is not None:
            val = fields[key]
            if cast:
                try:
                    val = cast(val)
                except:
                    return
            if details.get(key) != val:
                details[key] = val
                changed = True
    set_if("name", str)
    set_if("category", str)
    set_if("description_full", str)
    # keep short auto-derived
    if "description_full" in fields and fields["description_full"] is not None:
        full_desc = details["description_full"]
        details["description_short"] = (full_desc[:120] + "...") if len(full_desc) > 120 else full_desc
    set_if("price", float)
    set_if("stock", int)
    if "tags" in fields and fields["tags"] is not None:
        tags_list = [t.strip() for t in str(fields["tags"]).split(",") if t.strip()]
        details["tags"] = tags_list
        changed = True
    if changed:
        details["updated_at"] = now_iso()
        save_json(details_file, details)
    return details

def delete_item(retailer_username, item_id):
    folder = retailer_item_path(retailer_username, item_id)
    if folder.exists():
        shutil.rmtree(folder)
        return True
    return False


# --------------- Gemini Helpers ---------------
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_TIMEOUT = 15

def _gemini_generate(model_name: str, prompt_text: str):
    if not GEMINI_API_KEY:
        print("[Gemini] Missing API key.")
        return None
    url = f"{GEMINI_BASE_URL}/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt_text}]}
        ]
    }
    try:
        resp = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
        if resp.status_code != 200:
            print(f"[Gemini] Non-200 status {resp.status_code}: {resp.text[:300]}")
            return None
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return None
        return parts[0].get("text")
    except Exception as e:
        print("[Gemini] Error:", e)
        return None

def call_gemini_recommendation(history_messages, inventory_summary):
    preference = ""
    for m in reversed(history_messages):
        if m["role"] == "user":
            preference = m["content"]
            break
    compact = []
    for itm in inventory_summary:
        compact.append({
            "item_id": itm["item_id"],
            "name": itm["name"],
            "category": itm["category"],
            "price": itm["price"],
            "tags": itm.get("tags", [])[:8],
            "desc": itm.get("description_short", "")[:160],
            "retailer": itm.get("retailer")
        })
    instructions = (
        "You are an e-commerce recommendation assistant. "
        "Given INVENTORY (JSON array) + USER_PREFERENCE choose up to 3 items. "
        "Return ONLY JSON: {\"recommendations\":[{\"item_id\":\"...\",\"reason\":\"...\",\"match_score\":0-100}],"
        "\"follow_up_question\":\"...\"}. If nothing matches, recommendations=[] and ask clarifying follow_up_question."
    )
    prompt = (
        f"{instructions}\nINVENTORY:\n{json.dumps(compact, ensure_ascii=False)}\n"
        f"USER_PREFERENCE:\n{preference}\nRespond ONLY with JSON:"
    )
    raw = _gemini_generate(GEMINI_RECOMMEND_MODEL, prompt)
    if raw:
        raw_strip = raw.strip()
        candidate_json = None
        if raw_strip.startswith("{") and raw_strip.endswith("}"):
            candidate_json = raw_strip
        else:
            s = raw_strip.find("{"); e = raw_strip.rfind("}")
            if s != -1 and e != -1 and e > s:
                candidate_json = raw_strip[s:e+1]
        if candidate_json:
            try:
                parsed = json.loads(candidate_json)
                recs = []
                for rec in parsed.get("recommendations", [])[:3]:
                    if not isinstance(rec, dict): continue
                    iid = rec.get("item_id")
                    if not iid: continue
                    reason = (rec.get("reason") or "").strip()[:300]
                    try:
                        score = int(rec.get("match_score", 0))
                    except:
                        score = 0
                    score = max(0, min(score, 100))
                    recs.append({
                        "item_id": iid,
                        "reason": reason or "Relevant match",
                        "match_score": score
                    })
                parsed["recommendations"] = recs
                if "follow_up_question" not in parsed or not isinstance(parsed["follow_up_question"], str):
                    parsed["follow_up_question"] = "Would you like more details or a different type of item?"
                return parsed
            except json.JSONDecodeError:
                print("[Gemini] JSON parse fail.")
    # Fallback heuristic
    user_pref = preference.lower()
    keywords = [w for w in user_pref.split() if len(w) > 3]
    scored = []
    for item in inventory_summary:
        text = " ".join([
            item.get("name",""), item.get("category",""),
            " ".join(item.get("tags",[])), item.get("description_short","")
        ]).lower()
        score = sum(text.count(k) for k in keywords) * 10
        scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    recs = []
    for score, itm in scored[:3]:
        recs.append({
            "item_id": itm["item_id"],
            "reason": "Keyword relevance" if score > 0 else "General fit",
            "match_score": min(score, 100)
        })
    return {
        "recommendations": recs,
        "follow_up_question": "Would you like something different or more details?"
    }

def call_gemini_faq(question, static_faq):
    scope = (
        "You are a concise FAQ assistant for an e-commerce site (accounts, product listing, browsing, AI recommendations, purchase flow). "
        "If out of scope respond exactly: 'I can help only with platform usage, accounts, products, and purchase requests.' "
        "Max 120 words."
    )
    ref = "\n".join([f"Q:{f['q']}\nA:{f['a']}" for f in static_faq])
    prompt = f"{scope}\nREFERENCE FAQ:\n{ref}\nUSER QUESTION:\n{question}\nAnswer:"
    raw = _gemini_generate(GEMINI_FAQ_MODEL, prompt)
    if raw:
        ans = raw.strip()
        return ans[:600]
    q_lower = question.lower()
    for pair in static_faq:
        if pair["q"].lower() in q_lower:
            return pair["a"]
    return "I can help only with platform usage, accounts, products, and purchase requests."

# --------------- Chat Session Helpers ---------------
NON_PRODUCT_PATTERNS = [
    "what's my name","whats my name","who am i","how are you",
    "tell me a joke","my name","who are you"
]

def looks_non_product_query(message: str):
    m = message.lower().strip()
    product_keywords = ["tech","clothing","furniture","item","product","buy","price","laptop","shirt","table","phone","keyboard"]
    if any(pat in m for pat in NON_PRODUCT_PATTERNS) and not any(kw in m for kw in product_keywords):
        return True
    return False

def create_chat_session():
    session_id = str(uuid.uuid4())
    history = [{
        "role": "assistant",
        "content": "I have gathered all the details of items - can you describe what type of item you would like to purchase?"
    }]
    CHAT_SESSIONS[session_id] = {
        "history": history,
        "created_at": now_iso()
    }
    session['current_chat_session_id'] = session_id
    return session_id, history[-1]["content"]

def ensure_active_chat_session(provided_session_id: str | None):
    if provided_session_id and provided_session_id in CHAT_SESSIONS:
        return provided_session_id, CHAT_SESSIONS[provided_session_id], False
    stored_id = session.get("current_chat_session_id")
    if stored_id and stored_id in CHAT_SESSIONS:
        return stored_id, CHAT_SESSIONS[stored_id], False
    new_id, _ = create_chat_session()
    return new_id, CHAT_SESSIONS[new_id], True

# --------------- Orders & Cart ---------------
def load_orders_data():
    data = load_json(PURCHASE_FILE, {"requests": [], "orders": []})
    if "orders" not in data:
        data["orders"] = []
    return data

def save_orders_data(data):
    save_json(PURCHASE_FILE, data)

def create_order(user, items, contact):
    data = load_orders_data()
    order_id = str(uuid.uuid4())
    total_amount = sum(i.get("price",0) for i in items)
    order = {
        "order_id": order_id,
        "user": user,
        "items": [{
            "item_id": i["item_id"],
            "retailer": i["retailer"],
            "price": i.get("price",0)
        } for i in items],
        "contact": contact,
        "status": "pending_payment",
        "total_amount": total_amount,
        "created_at": now_iso()
    }
    data["orders"].append(order)
    save_orders_data(data)
    return order

def generate_qr_base64(data_text: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=2,
    )
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# --------------- Routes: Auth / Pages ---------------
@app.route("/")
def home():
    if "username" in session:
        if session.get("role") == "retailer":
            return redirect(url_for("retailer_store"))
        return redirect(url_for("user_app"))
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        role = request.form.get("role")
        if role not in ("user","retailer"):
            return render_template("register.html", error="Select a valid role.")
        if not username or not password:
            return render_template("register.html", error="Missing credentials.")
        success, msg = add_account(username, password, role)
        if success:
            return redirect(url_for("home"))
        return render_template("register.html", error=msg)
    return render_template("register.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username","").strip()
    password = request.form.get("password","").strip()
    role = request.form.get("role")
    acct = get_account(username)
    if not acct or acct["password"] != password or acct["role"] != role:
        return render_template("login.html", error="Invalid credentials or role mismatch.")
    session["username"] = username
    session["role"] = role
    update_last_login(username)
    return redirect(url_for("retailer_store" if role == "retailer" else "user_app"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/app")
def user_app():
    if session.get("role") != "user":
        return redirect(url_for("home"))
    items = list(iter_all_items())
    counts = load_json(COUNT_FILE, {})
    faqs = load_json(FAQ_FILE, {})
    cart = session.get("cart", [])
    return render_template("user_app.html",
                           items=items,
                           counts=counts.get("recommendation_ratings", {}),
                           faqs=faqs.get("static_faq", []),
                           cart_count=len(cart))

@app.route("/store")
def retailer_store():
    if session.get("role") != "retailer":
        return redirect(url_for("home"))
    username = session["username"]
    items = [i for i in iter_all_items() if i.get("retailer") == username]
    faqs = load_json(FAQ_FILE, {}).get("static_faq", [])
    counts = load_json(COUNT_FILE, {}).get("recommendation_ratings", {})
    return render_template("retailer_store.html", items=items, counts=counts, faqs=faqs)

# --------------- Product / Upload ---------------
@app.route("/store/upload", methods=["POST"])
def upload_product():
    if session.get("role") != "retailer":
        return abort(403)
    form = request.form
    image = request.files.get("image")
    if not form.get("name"):
        return jsonify({"ok": False, "error": "Name required"}), 400
    item = save_item(session["username"], {
        "name": form.get("name"),
        "category": form.get("category","other"),
        "description": form.get("description",""),
        "price": form.get("price","0"),
        "stock": form.get("stock","0"),
        "tags": form.get("tags","")
    }, image)
    return jsonify({"ok": True, "item": item})

@app.route("/product/<retailer>/<item_id>")
def product_page(retailer, item_id):
    item = get_item(retailer, item_id)
    if not item:
        abort(404)
    cart = session.get("cart", [])
    in_cart = any(c['item_id'] == item_id and c['retailer'] == retailer for c in cart)
    return render_template("product.html", item=item, in_cart=in_cart)

@app.route("/uploads/<retailer>/<item_id>/<filename>")
def serve_image(retailer, item_id, filename):
    folder = UPLOAD_DIR / retailer / item_id
    if not folder.exists():
        abort(404)
    return send_from_directory(str(folder), filename)

@app.route("/store/item/<item_id>/edit", methods=["POST"])
def edit_item(item_id):
    if session.get("role") != "retailer":
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    retailer_username = session["username"]
    payload = request.get_json() or {}
    # Map frontend field names to details.json keys
    fields = {
        "name": payload.get("name"),
        "category": payload.get("category"),
        "description_full": payload.get("description"),
        "price": payload.get("price"),
        "stock": payload.get("stock"),
        "tags": payload.get("tags")
    }
    updated = update_item(retailer_username, item_id, fields)
    if not updated:
        return jsonify({"ok": False, "error": "Item not found or update failed"}), 404
    return jsonify({"ok": True, "item": updated})

@app.route("/store/item/<item_id>/delete", methods=["POST"])
def delete_item_route(item_id):
    if session.get("role") != "retailer":
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    retailer_username = session["username"]
    success = delete_item(retailer_username, item_id)
    if not success:
        return jsonify({"ok": False, "error": "Item not found"}), 404
    return jsonify({"ok": True})
# --------------- Cart ---------------
@app.route("/cart")
def cart_page():
    if session.get("role") != "user":
        return redirect(url_for("home"))
    cart = session.get("cart", [])
    # Resolve item details
    resolved = []
    total = 0
    for c in cart:
        itm = get_item(c["retailer"], c["item_id"])
        if itm:
            resolved.append(itm)
            total += float(itm.get("price",0))
    return render_template("cart.html", items=resolved, total=total)

@app.route("/cart/add", methods=["POST"])
def cart_add():
    if session.get("role") != "user":
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    data = request.get_json() or {}
    item_id = data.get("item_id")
    retailer = data.get("retailer")
    if not item_id or not retailer:
        return jsonify({"ok": False, "error": "Missing data"}), 400
    item = get_item(retailer, item_id)
    if not item:
        return jsonify({"ok": False, "error": "Item not found"}), 404
    cart = session.get("cart", [])
    if not any(c['item_id']==item_id and c['retailer']==retailer for c in cart):
        cart.append({"item_id": item_id, "retailer": retailer})
    session["cart"] = cart
    return jsonify({"ok": True, "count": len(cart)})

@app.route("/cart/remove", methods=["POST"])
def cart_remove():
    if session.get("role") != "user":
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    data = request.get_json() or {}
    item_id = data.get("item_id")
    retailer = data.get("retailer")
    cart = session.get("cart", [])
    new_cart = [c for c in cart if not (c['item_id']==item_id and c['retailer']==retailer)]
    session["cart"] = new_cart
    return jsonify({"ok": True, "count": len(new_cart)})

@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    if session.get("role") != "user":
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    session["cart"] = []
    return jsonify({"ok": True})

# --------------- Order (Single Item) ---------------
@app.route("/order/<retailer>/<item_id>")
def order_page(retailer, item_id):
    if session.get("role") != "user":
        return redirect(url_for("home"))
    item = get_item(retailer, item_id)
    if not item:
        abort(404)
    return render_template("place_order.html", mode="single", items=[item], total=item.get("price",0))

@app.route("/order/create", methods=["POST"])
def order_create():
    if session.get("role") != "user":
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    data = request.get_json() or {}
    mode = data.get("mode","single")
    contact = {
        "name": data.get("name","").strip(),
        "phone": data.get("phone","").strip(),
        "email": data.get("email","").strip(),
        "address": data.get("address","").strip()
    }
    if not all(contact.values()):
        return jsonify({"ok": False, "error": "All contact fields required"}), 400

    items = []
    if mode == "single":
        retailer = data.get("retailer")
        item_id = data.get("item_id")
        item = get_item(retailer, item_id)
        if not item:
            return jsonify({"ok": False, "error": "Item not found"}), 404
        items = [item]
    else:
        # cart mode
        cart = session.get("cart", [])
        for c in cart:
            itm = get_item(c["retailer"], c["item_id"])
            if itm:
                items.append(itm)
        if not items:
            return jsonify({"ok": False, "error": "Cart is empty"}), 400

    order = create_order(session["username"], items, contact)
    return jsonify({"ok": True, "order_id": order["order_id"], "total": order["total_amount"]})

@app.route("/order/<order_id>/qr")
def order_qr(order_id):
    data = load_orders_data()
    order = next((o for o in data["orders"] if o["order_id"] == order_id), None)
    if not order:
        return jsonify({"ok": False, "error": "Order not found"}), 404
    # Encode a simple UPI data string. Customize as needed.
    # Example placeholder: <UPI_ID>|ORDER=<id>|AMT=<amount>
    payload = f"upi://pay?pa={UPI_ID}&pn=SmartShop&tr={order_id}&am={order['total_amount']}&cu=INR"
    img_b64 = generate_qr_base64(payload)
    return jsonify({"ok": True, "image": img_b64, "upi_payload": payload})

@app.route("/order/<order_id>/verify", methods=["POST"])
def order_verify(order_id):
    data = load_orders_data()
    order = next((o for o in data["orders"] if o["order_id"] == order_id), None)
    if not order:
        return jsonify({"ok": False, "error": "Order not found"}), 404
    # For now just respond with placeholder
    return jsonify({"ok": True, "message": "payment gateway is not set up - try again later"})

# --------------- Cart Checkout (Multi-item) ---------------
@app.route("/cart/checkout")
def cart_checkout():
    if session.get("role") != "user":
        return redirect(url_for("home"))
    cart = session.get("cart", [])
    resolved = []
    total = 0
    for c in cart:
        itm = get_item(c["retailer"], c["item_id"])
        if itm:
            resolved.append(itm)
            total += float(itm.get("price",0))
    if not resolved:
        return redirect(url_for("cart_page"))
    return render_template("place_order.html", mode="cart", items=resolved, total=total)

# --------------- Chat ---------------
@app.route("/chat/start", methods=["POST"])
def chat_start():
    if "username" not in session:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401
    session_id, first_msg = create_chat_session()
    return jsonify({"ok": True, "session_id": session_id, "message": first_msg})

@app.route("/chat/recommend", methods=["POST"])
def chat_recommend():
    if "username" not in session:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401
    data = request.get_json() or {}
    provided_session_id = data.get("session_id")
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"ok": False, "error": "Empty message"}), 400
    session_id, chat_obj, created_new = ensure_active_chat_session(provided_session_id)
    if created_new and provided_session_id:
        chat_obj["history"].append({
            "role": "assistant",
            "content": "The previous recommendation context expired. I started a fresh session. Please restate what you are looking for."
        })
    if looks_non_product_query(user_message):
        clarification = {
            "recommendations": [],
            "follow_up_question": "I’m here to recommend products. Tell me what kind of item you want (e.g. 'affordable tech keyboard', 'clothing item for winter')."
        }
        chat_obj["history"].append({"role":"user","content":user_message})
        chat_obj["history"].append({"role":"assistant","content":json.dumps(clarification)})
        return jsonify({"ok": True, "response": clarification, "session_id": session_id})

    chat_obj["history"].append({"role": "user", "content": user_message})
    inventory = []
    retailer_by_item = {}
    name_by_item = {}
    for item in iter_all_items():
        entry = {
            "item_id": item["item_id"],
            "name": item["name"],
            "category": item["category"],
            "tags": item.get("tags", []),
            "description_short": item.get("description_short",""),
            "price": item.get("price", 0),
            "stock": item.get("stock", 0),
            "retailer": item.get("retailer")
        }
        inventory.append(entry)
        retailer_by_item[item["item_id"]] = item.get("retailer")
        name_by_item[item["item_id"]] = item.get("name")
    model_response_struct = call_gemini_recommendation(chat_obj["history"], inventory)
    if not model_response_struct.get("recommendations"):
        model_response_struct.setdefault(
            "follow_up_question",
            "Could you please tell me what type of item you are looking for, including category or some keywords?"
        )
    enriched_recs = []
    for rec in model_response_struct.get("recommendations", []):
        rid = rec.get("item_id")
        retailer = retailer_by_item.get(rid)
        product_name = name_by_item.get(rid)
        product_url = url_for("product_page", retailer=retailer, item_id=rid, _external=True) if retailer else None
        enriched_recs.append({
            "item_id": rid,
            "name": product_name,
            "retailer": retailer,
            "product_url": product_url,
            "reason": rec.get("reason") or "Relevant match",
            "match_score": rec.get("match_score", 0)
        })
    model_response_struct["recommendations"] = enriched_recs
    chat_obj["history"].append({"role":"assistant","content":json.dumps(model_response_struct)})
    return jsonify({"ok": True, "response": model_response_struct, "session_id": session_id})

# --------------- Ratings / FAQ ---------------
@app.route("/chat/rate", methods=["POST"])
def chat_rate():
    data = request.get_json() or {}
    rating = data.get("rating","").lower()
    if rating not in ("excellent","good","bad"):
        return jsonify({"ok": False, "error": "Invalid rating"}), 400
    counts = load_json(COUNT_FILE, {})
    rec = counts.setdefault("recommendation_ratings", {"excellent":0,"good":0,"bad":0})
    rec[rating] = rec.get(rating, 0) + 1
    counts["last_updated"] = now_iso()
    save_json(COUNT_FILE, counts)
    return jsonify({"ok": True, "counts": rec})

@app.route("/faq/ask", methods=["POST"])
def faq_ask():
    data = request.get_json() or {}
    question = data.get("question","").strip()
    if not question:
        return jsonify({"ok": False, "error": "Empty question"}), 400
    faq_data = load_json(FAQ_FILE, {"static_faq": [], "dynamic_log": []})
    answer = call_gemini_faq(question, faq_data.get("static_faq", []))
    faq_data.setdefault("dynamic_log", []).append({
        "id": str(uuid.uuid4()),
        "user": session.get("username","anonymous"),
        "question": question,
        "answer": answer,
        "ts": now_iso()
    })
    save_json(FAQ_FILE, faq_data)
    return jsonify({"ok": True, "answer": answer})

# --------------- Counts Utility ---------------
@app.route("/counts")
def get_counts():
    counts = load_json(COUNT_FILE, {})
    return jsonify(counts.get("recommendation_ratings", {}))

if __name__ == "__main__":
    app.run(debug=True)