from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
import os

app = Flask(__name__)


# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")

SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variable."
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return render_template("L&F.html")


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
# CREATE ITEM
# ============================================================

@app.route("/api/items", methods=["POST"])
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
                str(data["contact"]).strip()

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
def delete_item(item_id):

    try:

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
        # Check already claimed
        # ----------------------------------------------------

        if item["status"] == "claimed":

            return jsonify({
                "success": False,
                "message": "Item has already been claimed"
            }), 400


        # ----------------------------------------------------
        # Update Supabase
        # ----------------------------------------------------

        update_data = {

            "status": "claimed",

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
                "Item claimed successfully",

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
# RUN FLASK
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True 
    )
