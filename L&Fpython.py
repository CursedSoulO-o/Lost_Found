items = []
next_id = 1


def report_item():
    global next_id

    print("\n--- Report an Item ---")
    item_type = input("Is it LOST or FOUND? ").strip().upper()

    while item_type not in ("LOST", "FOUND"):
        print("Please enter LOST or FOUND.")
        item_type = input("Is it LOST or FOUND? ").strip().upper()

    name = input("Item name: ").strip()
    category = input("Category: ").strip()
    description = input("Description: ").strip()
    location = input("Location: ").strip()
    date = input("Date (DD-MM-YYYY): ").strip()

    item = {
        "id": next_id,
        "type": item_type,
        "name": name,
        "category": category,
        "description": description,
        "location": location,
        "date": date,
        "status": "SEARCHING" if item_type == "LOST" else "AVAILABLE"
    }

    items.append(item)
    next_id += 1

    print(f"\nItem reported successfully! Item ID: {item['id']}")


def view_items():
    print("\n--- All Items ---")

    if not items:
        print("No items have been reported yet.")
        return

    for item in items:
        print("-" * 40)
        print(f"ID:          {item['id']}")
        print(f"Type:        {item['type']}")
        print(f"Name:        {item['name']}")
        print(f"Category:    {item['category']}")
        print(f"Description: {item['description']}")
        print(f"Location:    {item['location']}")
        print(f"Date:        {item['date']}")
        print(f"Status:      {item['status']}")


def search_items():
    print("\n--- Search Items ---")
    keyword = input("What are you looking for? ").strip().lower()

    found = False

    for item in items:
        searchable_text = (
            item["name"] + " " +
            item["category"] + " " +
            item["description"] + " " +
            item["location"]
        ).lower()

        if keyword in searchable_text:
            print("-" * 40)
            print(f"ID:       {item['id']}")
            print(f"Type:     {item['type']}")
            print(f"Name:     {item['name']}")
            print(f"Category: {item['category']}")
            print(f"Location: {item['location']}")
            print(f"Status:   {item['status']}")
            found = True

    if not found:
        print("No matching items found.")


def find_matches():
    print("\n--- Possible Matches ---")

    lost_items = [item for item in items if item["type"] == "LOST" and item["status"] == "SEARCHING"]
    found_items = [item for item in items if item["type"] == "FOUND" and item["status"] == "AVAILABLE"]

    if not lost_items or not found_items:
        print("You need at least one active LOST item and one active FOUND item.")
        return

    matches_found = False

    for lost in lost_items:
        for found in found_items:
            score = 0

            if lost["name"].lower() == found["name"].lower():
                score += 40

            if lost["category"].lower() == found["category"].lower():
                score += 20

            if lost["location"].lower() == found["location"].lower():
                score += 30

            if lost["date"] == found["date"]:
                score += 10

            if score >= 50:
                matches_found = True
                print("-" * 40)
                print(f"Possible match: {score}%")
                print(f"LOST  -> ID {lost['id']} | {lost['name']} | {lost['location']}")
                print(f"FOUND -> ID {found['id']} | {found['name']} | {found['location']}")

    if not matches_found:
        print("No strong matches found.")


def mark_returned():
    print("\n--- Mark Item as Returned ---")

    if not items:
        print("No items available.")
        return

    try:
        item_id = int(input("Enter item ID: "))
    except ValueError:
        print("Please enter a valid numeric ID.")
        return

    for item in items:
        if item["id"] == item_id:
            item["status"] = "RETURNED"
            print(f"Item {item_id} has been marked as RETURNED.")
            return

    print("Item ID not found.")


def main():
    while True:
        print("\n" + "=" * 45)
        print("       COLLEGE LOST & FOUND")
        print("=" * 45)
        print("1. Report Lost/Found Item")
        print("2. View All Items")
        print("3. Search Items")
        print("4. Find Possible Matches")
        print("5. Mark Item as Returned")
        print("6. Exit")

        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            report_item()
        elif choice == "2":
            view_items()
        elif choice == "3":
            search_items()
        elif choice == "4":
            find_matches()
        elif choice == "5":
            mark_returned()
        elif choice == "6":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please choose 1-6.")


if __name__ == "__main__":
    main()