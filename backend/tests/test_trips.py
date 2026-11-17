from datetime import date, timedelta

import pytest


def trip_data(**changes):
    data = {
        "name": "Manali Trip",
        "destination": "Manali",
        "start_date": "2026-12-01",
        "end_date": "2026-12-05",
        "budget": 15000,
        "description": "Snow",
    }
    return {**data, **changes}


def days_from_today(days):
    return (date.today() + timedelta(days=days)).isoformat()


def test_get_trips_empty(client):
    response = client.get("/api/trips")
    assert response.status_code == 200
    assert response.get_json() == []


def test_get_trips(client, trip):
    response = client.get("/api/trips")
    assert response.status_code == 200
    trips = response.get_json()
    assert len(trips) == 1
    assert trips[0]["name"] == "Goa Trip"


def test_create_trip(client):
    response = client.post("/api/trips", json=trip_data())
    assert response.status_code == 201
    trip = response.get_json()
    assert trip["id"] == 1
    assert trip["name"] == "Manali Trip"
    assert trip["budget"] == 15000
    assert trip["created_at"]


def test_create_trip_without_budget_defaults_to_zero(client):
    data = trip_data()
    del data["budget"]
    response = client.post("/api/trips", json=data)
    assert response.status_code == 201
    assert response.get_json()["budget"] == 0


def test_get_trip(client, trip):
    response = client.get(f"/api/trips/{trip['id']}")
    assert response.status_code == 200
    assert response.get_json()["destination"] == "Goa"


def test_update_trip(client, trip):
    data = trip_data(name="Goa Trip 2", destination="North Goa")
    response = client.put(f"/api/trips/{trip['id']}", json=data)
    assert response.status_code == 200
    assert response.get_json()["name"] == "Goa Trip 2"

    saved = client.get(f"/api/trips/{trip['id']}").get_json()
    assert saved["destination"] == "North Goa"


def test_delete_trip(client, trip):
    response = client.delete(f"/api/trips/{trip['id']}")
    assert response.status_code == 200
    assert client.get(f"/api/trips/{trip['id']}").status_code == 404


def test_delete_trip_deletes_its_activities(client, trip, activity):
    client.delete(f"/api/trips/{trip['id']}")
    assert client.put(f"/api/activities/{activity['id']}", json={}).status_code == 404


@pytest.mark.parametrize("changes, message", [
    ({"name": ""}, "Name is required"),
    ({"name": "   "}, "Name is required"),
    ({"destination": ""}, "Destination is required"),
    ({"start_date": ""}, "Start date is required"),
    ({"end_date": ""}, "End date is required"),
    ({"start_date": "10-11-2026"}, "Start date must be a valid date (YYYY-MM-DD)"),
    ({"end_date": "2026-11-31"}, "End date must be a valid date (YYYY-MM-DD)"),
    ({"start_date": "2026-12-10", "end_date": "2026-12-01"}, "End date cannot be before start date"),
    ({"budget": -1}, "Budget cannot be negative"),
    ({"budget": "lots"}, "Budget must be a number"),
    ({"timezone": "Not/A_Zone"}, "Timezone must be a valid timezone"),
    ({"timezone": "Mars/Base"}, "Timezone must be a valid timezone"),
    ({"timezone": "UTC+1"}, "Timezone must be a valid timezone"),
    ({"timezone": 123}, "Timezone must be a valid timezone"),
    ({"timezone": True}, "Timezone must be a valid timezone"),
    ({"timezone": ["America/New_York"]}, "Timezone must be a valid timezone"),
    ({"timezone": "../../etc/passwd"}, "Timezone must be a valid timezone"),
])
def test_create_trip_invalid_data(client, changes, message):
    response = client.post("/api/trips", json=trip_data(**changes))
    assert response.status_code == 400
    assert response.get_json() == {"error": message}


def test_create_trip_without_json_body(client):
    response = client.post("/api/trips", data="not json")
    assert response.status_code == 400


def test_update_trip_invalid_data(client, trip):
    response = client.put(f"/api/trips/{trip['id']}", json=trip_data(budget=-5))
    assert response.status_code == 400
    assert client.get(f"/api/trips/{trip['id']}").get_json()["budget"] == 20000


def test_trip_not_found(client):
    assert client.get("/api/trips/999").status_code == 404
    assert client.put("/api/trips/999", json=trip_data()).status_code == 404
    response = client.delete("/api/trips/999")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Trip not found"}


def test_invalid_trip_id(client):
    for bad_id in ("abc", "0", "-3"):
        response = client.get(f"/api/trips/{bad_id}")
        assert response.status_code == 400
        assert response.get_json() == {"error": "Invalid trip id"}


def test_update_trip_dates_cannot_leave_activities_outside(client, trip, activity):
    # the activity is on 2026-11-10, the first day of the trip
    data = trip_data(start_date="2026-11-11", end_date="2026-11-14")
    response = client.put(f"/api/trips/{trip['id']}", json=data)
    assert response.status_code == 400
    assert "activities fall outside" in response.get_json()["error"]
    assert client.get(f"/api/trips/{trip['id']}").get_json()["start_date"] == "2026-11-10"


def test_update_trip_dates_allowed_when_activities_still_fit(client, trip, activity):
    wider = trip_data(start_date="2026-11-01", end_date="2026-11-30")
    assert client.put(f"/api/trips/{trip['id']}", json=wider).status_code == 200

    narrower = trip_data(start_date="2026-11-10", end_date="2026-11-10")
    assert client.put(f"/api/trips/{trip['id']}", json=narrower).status_code == 200


def test_huge_numbers_are_rejected_not_server_errors(client):
    assert client.post("/api/trips", json=trip_data(budget=10**30)).status_code == 400
    assert client.post("/api/trips", json=trip_data(budget=1e300)).status_code == 400
    assert client.get("/api/trips/99999999999999999999").status_code == 400


def test_id_must_be_plain_digits(client):
    assert client.get("/api/trips/1_0").status_code == 400
    assert client.get("/api/trips/+1").status_code == 400


def test_search_treats_wildcards_as_plain_text(client, trip):
    client.post("/api/trips", json=trip_data(name="100% Fun"))
    client.post("/api/trips", json=trip_data(name="Ski_Trip"))

    assert [t["name"] for t in client.get("/api/trips?search=%25").get_json()] == ["100% Fun"]
    assert [t["name"] for t in client.get("/api/trips?search=i_T").get_json()] == ["Ski_Trip"]


def test_search_trips(client, trip):
    client.post("/api/trips", json=trip_data())

    by_name = client.get("/api/trips?search=goa").get_json()
    assert [t["name"] for t in by_name] == ["Goa Trip"]

    by_destination = client.get("/api/trips?search=MANALI").get_json()
    assert [t["destination"] for t in by_destination] == ["Manali"]

    assert client.get("/api/trips?search=paris").get_json() == []


def test_filter_trips_by_status(client):
    client.post("/api/trips", json=trip_data(name="Past", start_date=days_from_today(-10), end_date=days_from_today(-5)))
    client.post("/api/trips", json=trip_data(name="Now", start_date=days_from_today(-1), end_date=days_from_today(1)))
    client.post("/api/trips", json=trip_data(name="Next", start_date=days_from_today(5), end_date=days_from_today(9)))

    def names(status):
        return [t["name"] for t in client.get(f"/api/trips?status={status}").get_json()]

    assert names("completed") == ["Past"]
    assert names("ongoing") == ["Now"]
    assert names("upcoming") == ["Next"]


def test_trip_status_includes_first_and_last_day(client):
    today = days_from_today(0)
    client.post("/api/trips", json=trip_data(name="Starts today", start_date=today, end_date=days_from_today(3)))
    client.post("/api/trips", json=trip_data(name="Ends today", start_date=days_from_today(-3), end_date=today))

    ongoing = client.get("/api/trips?status=ongoing").get_json()
    assert sorted(t["name"] for t in ongoing) == ["Ends today", "Starts today"]


def test_invalid_status_filter(client):
    response = client.get("/api/trips?status=someday")
    assert response.status_code == 400


def test_unknown_route_returns_json(client):
    response = client.get("/api/nothing")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Not Found"}


def test_create_trip_with_timezone(client):
    response = client.post("/api/trips", json=trip_data(timezone="America/New_York"))
    assert response.status_code == 201
    trip = response.get_json()
    assert trip["timezone"] == "America/New_York"

    saved = client.get(f"/api/trips/{trip['id']}").get_json()
    assert saved["timezone"] == "America/New_York"

    all_trips = client.get("/api/trips").get_json()
    assert any(t["id"] == trip["id"] and t["timezone"] == "America/New_York" for t in all_trips)


def test_create_trip_default_timezone_when_omitted(client):
    response = client.post("/api/trips", json=trip_data())
    assert response.status_code == 201
    assert response.get_json()["timezone"] == "UTC"


def test_create_trip_empty_or_whitespace_timezone_defaults_to_utc(client):
    res_empty = client.post("/api/trips", json=trip_data(timezone=""))
    assert res_empty.status_code == 201
    assert res_empty.get_json()["timezone"] == "UTC"

    res_spaces = client.post("/api/trips", json=trip_data(timezone="   "))
    assert res_spaces.status_code == 201
    assert res_spaces.get_json()["timezone"] == "UTC"

    res_none = client.post("/api/trips", json=trip_data(timezone=None))
    assert res_none.status_code == 201
    assert res_none.get_json()["timezone"] == "UTC"


def test_create_trip_strips_whitespace_from_valid_timezone(client):
    response = client.post("/api/trips", json=trip_data(timezone="  America/New_York  "))
    assert response.status_code == 201
    assert response.get_json()["timezone"] == "America/New_York"


@pytest.mark.parametrize("tz", [
    "America/New_York",
    "Europe/London",
    "Asia/Tokyo",
    "Australia/Sydney",
    "Asia/Kolkata",
    "UTC",
    "GMT",
    "Etc/UTC",
])
def test_create_trip_supports_various_valid_timezones(client, tz):
    response = client.post("/api/trips", json=trip_data(timezone=tz))
    assert response.status_code == 201
    assert response.get_json()["timezone"] == tz


def test_update_trip_timezone(client, trip):
    # trip fixture created without timezone defaults to UTC
    assert trip["timezone"] == "UTC"

    # Update to America/New_York
    update_data = trip_data(timezone="America/New_York")
    response = client.put(f"/api/trips/{trip['id']}", json=update_data)
    assert response.status_code == 200
    assert response.get_json()["timezone"] == "America/New_York"

    saved = client.get(f"/api/trips/{trip['id']}").get_json()
    assert saved["timezone"] == "America/New_York"

    # Update to Europe/London
    update_data["timezone"] = "Europe/London"
    response2 = client.put(f"/api/trips/{trip['id']}", json=update_data)
    assert response2.status_code == 200
    assert response2.get_json()["timezone"] == "Europe/London"


def test_update_trip_invalid_timezone(client, trip):
    response = client.put(f"/api/trips/{trip['id']}", json=trip_data(timezone="Invalid/Timezone"))
    assert response.status_code == 400
    assert response.get_json() == {"error": "Timezone must be a valid timezone"}

    # Ensure original timezone was not altered
    saved = client.get(f"/api/trips/{trip['id']}").get_json()
    assert saved["timezone"] == "UTC"


def test_existing_trips_without_timezone_default_to_utc(client):
    from database import get_db
    with client.application.app_context():
        db = get_db()
        cursor = db.execute(
            """INSERT INTO trips (name, destination, start_date, end_date, budget, description)
               VALUES ('Legacy Trip', 'Old City', '2026-12-01', '2026-12-05', 1000, 'Ancient')"""
        )
        db.commit()
        legacy_id = cursor.lastrowid

    response = client.get(f"/api/trips/{legacy_id}")
    assert response.status_code == 200
    assert response.get_json()["timezone"] == "UTC"

    all_trips = client.get("/api/trips").get_json()
    legacy_trip = next(t for t in all_trips if t["id"] == legacy_id)
    assert legacy_trip["timezone"] == "UTC"


def test_database_migration_adds_default_timezone_to_old_schema(tmp_path):
    import sqlite3
    from app import create_app

    old_db_path = str(tmp_path / "old_schema.db")
    # Simulate an old database created with the previous schema (no timezone column)
    conn = sqlite3.connect(old_db_path)
    conn.executescript("""
        CREATE TABLE trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            destination TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            budget NUMERIC NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO trips (name, destination, start_date, end_date, budget, description)
        VALUES ('Pre-migration Trip', 'Paris', '2026-05-01', '2026-05-10', 3000, 'Before TZ');
    """)
    conn.close()

    # Now start app with this database, triggering init_db migration
    app = create_app(old_db_path)
    test_client = app.test_client()

    response = test_client.get("/api/trips/1")
    assert response.status_code == 200
    trip = response.get_json()
    assert trip["name"] == "Pre-migration Trip"
    assert trip["timezone"] == "UTC"


def test_activity_time_stored_separately_from_trip_timezone(client):
    # Trip is in New York timezone
    trip_res = client.post("/api/trips", json=trip_data(
        destination="New York",
        timezone="America/New_York",
        start_date="2026-12-01",
        end_date="2026-12-05",
    ))
    trip_id = trip_res.get_json()["id"]

    # Activity has simple local time
    act_res = client.post(f"/api/trips/{trip_id}/activities", json={
        "title": "Visit Empire State",
        "date": "2026-12-02",
        "time": "14:30",
        "location": "Empire State Building",
        "notes": "Observation deck",
    })
    assert act_res.status_code == 201
    activity = act_res.get_json()

    # Time remains simple local "14:30", not modified or merged with timezone
    assert activity["time"] == "14:30"
    assert "timezone" not in activity

    # Verify directly from database table that activities table does not store timezone
    from database import get_db
    with client.application.app_context():
        db = get_db()
        act_row = db.execute("SELECT * FROM activities WHERE id = ?", (activity["id"],)).fetchone()
        columns = act_row.keys()
        assert "timezone" not in columns
        assert act_row["time"] == "14:30"

