from src.database import init_db
from src.agent import ask


def main():
    print("טוען נתונים...")
    init_db()
    print("סוכן מידע גאוגרפי מוכן. הקלד שאלה בעברית (או 'יציאה' לסיום).\n")

    while True:
        try:
            question = input("שאלה: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nלהתראות!")
            break

        if not question:
            continue
        if question in ("יציאה", "exit", "quit"):
            print("להתראות!")
            break

        result = ask(question)

        print(f"\n--- SQL ---\n{result['sql']}")
        if result["results"]:
            print(f"\n--- תוצאות ---\n{result['results']}")
        print(f"\n--- תשובה ---\n{result['answer']}\n")


if __name__ == "__main__":
    main()
