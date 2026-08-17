from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
from functools import wraps
import os

try:
    from dotenv import load_dotenv

    # Local dev: Vercel deploys inject env vars automatically, but
    # running `python app.py` locally needs them loaded from a .env
    # file ourselves. Try .env.local first (what the Vercel CLI
    # writes), then fall back to a plain .env.
    load_dotenv(".env.local")
    load_dotenv()
except ImportError:
    # python-dotenv isn't installed (e.g. on Vercel, where it's not
    # needed) -- environment variables are expected to already be set.
    pass

app = Flask(__name__)


# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")

SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Used only for auth calls (sign up / sign in). Falls back to the
# service role key if no anon key is configured, since the GoTrue
# auth endpoints work with either.
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or SUPABASE_KEY

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variable. "
        "Add them to .env.local (SUPABASE_URL=... and "
        "SUPABASE_SERVICE_ROLE_KEY=...) for local development, or set them "
        "in your Vercel project's Environment Variables for deployment."
    )

# Service-role client: used for all data reads/writes (bypasses RLS).
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# Auth client: used only for sign up / sign in / token verification.
supabase_auth: Client = create_client(
    SUPABASE_URL,
    SUPABASE_ANON_KEY
)


# ============================================================
# AUTH HELPERS
# ============================================================

def get_bearer_token():
    """Pull the raw JWT out of the Authorization: Bearer <token> header."""

    header = request.headers.get("Authorization", "")

    if not header.startswith("Bearer "):
        return None

    return header.split(" ", 1)[1].strip()


def get_current_user():
    """
    Verify the request's access token with Supabase and return the
    auth user object, or None if there's no valid session.
    """

    token = get_bearer_token()

    if not token:
        return None

    try:
        result = supabase_auth.auth.get_user(token)
        return result.user if result else None

    except Exception as e:
        print("AUTH VERIFY ERROR:", e)
        return None


def get_profile(user_id):
    """Fetch a user's profile row (contains their role)."""

    try:
        response = (
            supabase
            .table("profiles")
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        data = response.data or []
        return data[0] if data else None

    except Exception as e:
        print("GET PROFILE ERROR:", e)
        return None


def login_required(view_func):
    """Require a valid Supabase session. Attaches request.user."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):

        user = get_current_user()

        if not user:
            return jsonify({
                "success": False,
                "message": "You must be signed in to do that."
            }), 401

        request.user = user
        return view_func(*args, **kwargs)

    return wrapped


def admin_required(view_func):
    """Require a valid session belonging to an admin. Attaches request.user/profile."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):

        user = get_current_user()

        if not user:
            return jsonify({
                "success": False,
                "message": "You must be signed in to do that."
            }), 401

        profile = get_profile(user.id)

        if not profile or profile.get("role") != "admin":
            return jsonify({
                "success": False,
                "message": "Admin access required."
            }), 403

        request.user = user
        request.profile = profile
        return view_func(*args, **kwargs)

    return wrapped


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return render_template("L&F.html")


# ============================================================
# AUTH: SIGN UP
# ============================================================

@app.route("/api/auth/signup", methods=["POST"])
def signup():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "No data received"
        }), 400

    email = str(data.get("email", "")).strip()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must be at least 6 characters"
        }), 400

    try:
        result = supabase_auth.auth.sign_up({
            "email": email,
            "password": password
        })

        if not result.user:
            return jsonify({
                "success": False,
                "message": "Could not create account"
            }), 400

        # Session is None if the project requires email confirmation
        session = result.session

        return jsonify({
            "success": True,
            "message": (
                "Account created!"
                if session else
                "Account created! Check your email to confirm before signing in."
            ),
            "access_token": session.access_token if session else None,
            "user": {
                "id": result.user.id,
                "email": result.user.email,
                "role": "user"
            }
        }), 201

    except Exception as e:
        print("SIGNUP ERROR:", e)
        return jsonify({
            "success": False,
            "message": "Could not create account",
            "error": str(e)
        }), 400


# ============================================================
# AUTH: LOG IN
# ============================================================

@app.route("/api/auth/login", methods=["POST"])
def login():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "No data received"
        }), 400

    email = str(data.get("email", "")).strip()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required"
        }), 400

    try:
        result = supabase_auth.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not result.session:
            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        profile = get_profile(result.user.id)
        role = profile.get("role") if profile else "user"

        return jsonify({
            "success": True,
            "message": "Signed in successfully",
            "access_token": result.session.access_token,
            "user": {
                "id": result.user.id,
                "email": result.user.email,
                "role": role
            }
        })

    except Exception as e:
        print("LOGIN ERROR:", e)
        return jsonify({
            "success": False,
            "message": "Invalid email or password"
        }), 401


# ============================================================
# AUTH: CURRENT USER
# ============================================================

@app.route("/api/auth/me", methods=["GET"])
@login_required
def me():

    profile = get_profile(request.user.id)
    role = profile.get("role") if profile else "user"

    return jsonify({
        "success": True,
        "user": {
            "id": request.user.id,
            "email": request.user.email,
            "role": role
        }
    })


# ============================================================
# GET ALL ITEMS
# ============================================================

@app.route("/api/items", methods=["GET"])
def get_items():

    status = request.args.get("status", "").lower().strip()
    category = request.args.get("category", "").lower().strip()
    query = request.args.get("q", "").lower().strip()

    try:

        response = (
            supabase
            .table("items")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        results = response.data or []


        # ----------------------------------------------------
        # Filter by status
        # ----------------------------------------------------

        if status:

            results = [
                item for item in results
                if item.get("status", "").lower() == status
            ]


        # ----------------------------------------------------
        # Filter by category
        # ----------------------------------------------------

        if category:

            results = [
                item for item in results
                if item.get("category", "").lower() == category
            ]


        # ----------------------------------------------------
        # Search
        # ----------------------------------------------------

        if query:

            results = [

                item for item in results

                if query in (
                    str(item.get("title", "")) + " " +
                    str(item.get("description", "")) + " " +
                    str(item.get("location", "")) + " " +
                    str(item.get("category", "")) + " " +
                    str(item.get("case_no", ""))
                ).lower()

            ]


        return jsonify({
            "success": True,
            "count": len(results),
            "items": results
        })


    except Exception as e:

        print("GET ITEMS ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Could not load items",
            "error": str(e)
        }), 500


# ============================================================
# GET ONE ITEM
# ============================================================

@app.route("/api/items/<int:item_id>", methods=["GET"])
def get_item(item_id):

    try:

        response = (
            supabase
            .table("items")
            .select("*")
            .eq("id", item_id)
            .limit(1)
            .execute()
        )

        data = response.data or []


        if not data:

            return jsonify({
                "success": False,
                "message": "Item not found"
            }), 404


        return jsonify({
            "success": True,
            "item": data[0]
        })


    except Exception as e:

        print("GET ITEM ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Could not load item",
            "error": str(e)
        }), 500


# ============================================================
# GET MY ITEMS
# ============================================================

@app.route("/api/items/mine", methods=["GET"])
@login_required
def get_my_items():

    try:

        response = (
            supabase
            .table("items")
            .select("*")
            .eq("user_id", request.user.id)
            .order("created_at", desc=True)
            .execute()
        )

        return jsonify({
            "success": True,
            "items": response.data or []
        })

    except Exception as e:

        print("GET MY ITEMS ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Could not load your items",
            "error": str(e)
        }), 500


# ============================================================
# CREATE ITEM
# ============================================================

@app.route("/api/items", methods=["POST"])
@login_required
def create_item():

    data = request.get_json()


    if not data:

        return jsonify({
            "success": False,
            "message": "No data received"
        }), 400


    required_fields = [
        "title",
        "description",
        "category",
        "location",
        "date",
        "contact",
        "status"
    ]


    # --------------------------------------------------------
    # Validate fields
    # --------------------------------------------------------

    for field in required_fields:

        if field not in data or not data[field]:

            return jsonify({
                "success": False,
                "message": f"Missing field: {field}"
            }), 400


    item_status = str(
        data["status"]
    ).lower().strip()


    if item_status not in ["lost", "found"]:

        return jsonify({
            "success": False,
            "message": "Status must be lost or found"
        }), 400


    try:

        # ----------------------------------------------------
        # Insert into Supabase
        #
        # DO NOT send:
        # id
        # case_no
        # created_at
        #
        # Supabase generates those automatically.
        # ----------------------------------------------------

        item_data = {

            "title": str(data["title"]).strip(),

            "description":
                str(data["description"]).strip(),

            "category":
                str(data["category"]).lower().strip(),

            "status":
                item_status,

            "location":
                str(data["location"]).strip(),

            "date":
                data["date"] or None,

            "contact":
                str(data["contact"]).strip(),

            "user_id":
                request.user.id

        }


        response = (
            supabase
            .table("items")
            .insert(item_data)
            .execute()
        )


        created_items = response.data or []


        if not created_items:

            return jsonify({
                "success": False,
                "message": "Item was not created"
            }), 500


        return jsonify({
            "success": True,
            "message": "Item created successfully",
            "item": created_items[0]
        }), 201


    except Exception as e:

        print("CREATE ITEM ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Could not create item",
            "error": str(e)
        }), 500


# ============================================================
# DELETE ITEM
# ============================================================

@app.route("/api/items/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id):

    try:

        # ------------------------------------------------------------
        # Only the reporter or an admin may delete an item
        # ------------------------------------------------------------

        existing_response = (
            supabase
            .table("items")
            .select("user_id")
            .eq("id", item_id)
            .limit(1)
            .execute()
        )

        existing = existing_response.data or []

        if not existing:
            return jsonify({
                "success": False,
                "message": "Item not found"
            }), 404

        is_owner = existing[0].get("user_id") == request.user.id

        if not is_owner:
            profile = get_profile(request.user.id)

            if not profile or profile.get("role") != "admin":
                return jsonify({
                    "success": False,
                    "message": "You can only delete items you reported"
                }), 403

        response = (
            supabase
            .table("items")
            .delete()
            .eq("id", item_id)
            .execute()
        )


        deleted = response.data or []


        if not deleted:

            return jsonify({
                "success": False,
                "message": "Item not found"
            }), 404


        return jsonify({
            "success": True,
            "message": "Item deleted successfully"
        })


    except Exception as e:

        print("DELETE ITEM ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Could not delete item",
            "error": str(e)
        }), 500


# ============================================================
# SEARCH
# ============================================================

@app.route("/api/search", methods=["GET"])
def search_items():

    query = request.args.get(
        "q",
        ""
    ).lower().strip()


    if not query:

        return jsonify({
            "success": False,
            "message": "Please provide a search query"
        }), 400


    try:

        response = (
            supabase
            .table("items")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )


        items = response.data or []


        results = []


        for item in items:

            searchable_text = (

                str(item.get("title", "")) + " " +

                str(item.get("description", "")) + " " +

                str(item.get("category", "")) + " " +

                str(item.get("location", ""))

            ).lower()


            if query in searchable_text:

                results.append(item)


        return jsonify({

            "success": True,

            "count": len(results),

            "items": results

        })


    except Exception as e:

        print("SEARCH ERROR:", e)

        return jsonify({

            "success": False,

            "message": "Search failed",

            "error": str(e)

        }), 500


# ============================================================
# MATCHING SYSTEM
# ============================================================

@app.route("/api/matches/<int:item_id>", methods=["GET"])
def find_matches(item_id):

    try:

        # ----------------------------------------------------
        # Get target item
        # ----------------------------------------------------

        target_response = (
            supabase
            .table("items")
            .select("*")
            .eq("id", item_id)
            .limit(1)
            .execute()
        )


        target_data = target_response.data or []


        if not target_data:

            return jsonify({
                "success": False,
                "message": "Item not found"
            }), 404


        target = target_data[0]


        # ----------------------------------------------------
        # Get opposite status
        # ----------------------------------------------------

        opposite_status = (

            "found"

            if target["status"] == "lost"

            else "lost"

        )


        matches_response = (
            supabase
            .table("items")
            .select("*")
            .eq("status", opposite_status)
            .execute()
        )


        possible_matches = (
            matches_response.data or []
        )


        matches = []


        # ----------------------------------------------------
        # Calculate match score
        # ----------------------------------------------------

        for item in possible_matches:

            if item["id"] == target["id"]:
                continue


            score = 0


            # Title
            if (

                str(target.get("title", "")).lower()

                ==

                str(item.get("title", "")).lower()

            ):

                score += 40


            # Category
            if (

                str(target.get("category", "")).lower()

                ==

                str(item.get("category", "")).lower()

            ):

                score += 20


            # Location
            if (

                str(target.get("location", "")).lower()

                ==

                str(item.get("location", "")).lower()

            ):

                score += 30


            # Date
            if target.get("date") == item.get("date"):

                score += 10


            if score >= 50:

                matches.append({

                    "match_score": score,

                    "item": item

                })


        matches.sort(

            key=lambda x: x["match_score"],

            reverse=True

        )


        return jsonify({

            "success": True,

            "target_item": target,

            "matches": matches

        })


    except Exception as e:

        print("MATCH ERROR:", e)

        return jsonify({

            "success": False,

            "message": "Could not find matches",

            "error": str(e)

        }), 500


# ============================================================
# CLAIM ITEM
# ============================================================

@app.route("/api/items/<int:item_id>/claim", methods=["POST"])
@login_required
def claim_item(item_id):

    data = request.get_json()


    if not data:

        return jsonify({
            "success": False,
            "message": "No claim data received"
        }), 400


    claimant_name = data.get(
        "claimant_name"
    )

    claimant_contact = data.get(
        "claimant_contact"
    )

    message = data.get(
        "message",
        ""
    )


    if not claimant_name or not claimant_contact:

        return jsonify({
            "success": False,
            "message": "Name and contact are required"
        }), 400


    try:

        # ----------------------------------------------------
        # Check item exists
        # ----------------------------------------------------

        item_response = (
            supabase
            .table("items")
            .select("*")
            .eq("id", item_id)
            .limit(1)
            .execute()
        )


        items_found = (
            item_response.data or []
        )


        if not items_found:

            return jsonify({
                "success": False,
                "message": "Item not found"
            }), 404


        item = items_found[0]


        # ----------------------------------------------------
        # Check already claimed / already pending review
        # ----------------------------------------------------

        if item["status"] == "claimed":

            return jsonify({
                "success": False,
                "message": "Item has already been claimed"
            }), 400

        if item.get("claim_status") == "pending":

            return jsonify({
                "success": False,
                "message": "This item already has a claim awaiting admin review"
            }), 400


        # ----------------------------------------------------
        # Update Supabase
        #
        # Claiming no longer marks the item "claimed" directly.
        # It goes to "pending" review so an admin can verify the
        # claimant before the item is handed over.
        # ----------------------------------------------------

        update_data = {

            "claim_status": "pending",

            "claimant_user_id":
                request.user.id,

            "claimant_name":
                claimant_name,

            "claimant_contact":
                claimant_contact,

            "claim_message":
                message

        }


        update_response = (
            supabase
            .table("items")
            .update(update_data)
            .eq("id", item_id)
            .execute()
        )


        updated_items = (
            update_response.data or []
        )


        if not updated_items:

            return jsonify({
                "success": False,
                "message": "Could not claim item"
            }), 500


        return jsonify({

            "success": True,

            "message":
                "Claim submitted! An admin will review it shortly.",

            "item":
                updated_items[0]

        })


    except Exception as e:

        print("CLAIM ERROR:", e)

        return jsonify({

            "success": False,

            "message":
                "Could not claim item",

            "error":
                str(e)

        }), 500


# ============================================================
# ADMIN: LIST PENDING CLAIMS
# ============================================================

@app.route("/api/admin/claims", methods=["GET"])
@admin_required
def list_pending_claims():

    try:

        response = (
            supabase
            .table("items")
            .select("*")
            .eq("claim_status", "pending")
            .order("created_at", desc=True)
            .execute()
        )

        return jsonify({
            "success": True,
            "items": response.data or []
        })

    except Exception as e:

        print("LIST CLAIMS ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Could not load pending claims",
            "error": str(e)
        }), 500


# ============================================================
# ADMIN: APPROVE CLAIM
# ============================================================

@app.route("/api/admin/claims/<int:item_id>/approve", methods=["POST"])
@admin_required
def approve_claim(item_id):

    try:

        response = (
            supabase
            .table("items")
            .update({
                "status": "claimed",
                "claim_status": "approved"
            })
            .eq("id", item_id)
            .eq("claim_status", "pending")
            .execute()
        )

        updated = response.data or []

        if not updated:
            return jsonify({
                "success": False,
                "message": "No pending claim found for this item"
            }), 404

        return jsonify({
            "success": True,
            "message": "Claim approved. Item marked as claimed.",
            "item": updated[0]
        })

    except Exception as e:

        print("APPROVE CLAIM ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Could not approve claim",
            "error": str(e)
        }), 500


# ============================================================
# ADMIN: REJECT CLAIM
# ============================================================

@app.route("/api/admin/claims/<int:item_id>/reject", methods=["POST"])
@admin_required
def reject_claim(item_id):

    try:

        response = (
            supabase
            .table("items")
            .update({
                "claim_status": "rejected",
                "claimant_user_id": None,
                "claimant_name": None,
                "claimant_contact": None,
                "claim_message": None
            })
            .eq("id", item_id)
            .eq("claim_status", "pending")
            .execute()
        )

        updated = response.data or []

        if not updated:
            return jsonify({
                "success": False,
                "message": "No pending claim found for this item"
            }), 404

        return jsonify({
            "success": True,
            "message": "Claim rejected. Item is available again.",
            "item": updated[0]
        })

    except Exception as e:

        print("REJECT CLAIM ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Could not reject claim",
            "error": str(e)
        }), 500


# ============================================================
# RUN FLASK
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True 
    )