import uuid
from datetime import date, timedelta
from database.db import init_db, save_user, save_user_profile, save_workout_log, save_pr

def seed():
    print("Initializing database...")
    init_db()

    user_id = "test_user_001"
    name = "测试用户"

    print("Creating test user...")
    save_user(user_id, name)
    save_user_profile(user_id, {
        "height_cm": 175,
        "weight_kg": 75,
        "birth_date": "1999-03-15",
        "training_start_date": "2024-09-01",
        "squat_1rm": 100,
        "bench_1rm": 80,
        "deadlift_1rm": 120,
        "days_per_week": 4,
        "current_goal": "hypertrophy",
    })

    print("Inserting workout logs for past 28 days...")
    import random
    random.seed(42)
    today = date.today()
    for i in range(28):
        d = today - timedelta(days=27 - i)
        rate = round(random.uniform(0.8, 1.0), 2)
        save_workout_log({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "log_date": str(d),
            "sleep_score": random.randint(5, 9),
            "stress_score": random.randint(2, 6),
            "fatigue_score": random.randint(2, 6),
            "pain_areas": "",
            "planned_json": "[]",
            "actual_json": "[]",
            "completion_rate": rate,
            "is_override": False,
            "replan_count": 0,
            "note": None,
        })

    print("Inserting PR records...")
    exercises_pr = [
        ("卧推", [(75, 5), (78, 5), (80, 5)]),
        ("深蹲", [(90, 5), (95, 5), (100, 5)]),
        ("硬拉", [(110, 5), (115, 5), (120, 5)]),
    ]
    for exercise, records in exercises_pr:
        for i, (weight, reps) in enumerate(records):
            pr_date = today - timedelta(weeks=2 * (2 - i))
            conn = __import__("mysql.connector").connect(
                host="localhost", port=3306,
                user="root", password="",
                database="ai_fitness_coach",
            )
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO prs (id, user_id, exercise_name, weight_kg, reps, pr_date) VALUES (%s, %s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), user_id, exercise, weight, reps, str(pr_date)),
            )
            conn.commit()
            cursor.close()
            conn.close()

    print("Seed data inserted successfully!")
    print(f"Test user ID: {user_id}")

if __name__ == "__main__":
    seed()
