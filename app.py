import json
import mysql.connector
from mysql.connector import Error
from flask import Flask, request, jsonify
from redis import Redis

# Initialize Flask app and Redis client
app = Flask(__name__)
redis = Redis(host='redis', port=6379)

# Database configuration (test/development setup)
db_config = {
    'host': 'db',
    'user': 'admin',
    'password': 'admin',
    'database': 'test-db',
    'auth_plugin': 'mysql_native_password'
}

# Bootstrap: Create and initialize the "records" table
db = mysql.connector.connect(**db_config)
cursor = db.cursor()
cursor.execute('DROP TABLE IF EXISTS records')
cursor.execute('''
    CREATE TABLE records (
        recordId VARCHAR(255) PRIMARY KEY,
        time DATETIME(3),
        sourceId VARCHAR(255),
        destinationId VARCHAR(255),
        type ENUM('positive', 'negative'),
        value INT,
        unit VARCHAR(64),
        reference VARCHAR(255)
    )
''')
db.commit()
cursor.close()
db.close()

# Redis pub/sub notifier for new records
def emit_record_created_notification(recordId, destinationId, reference):
    channel = "record-stored-notification"
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Aggregate stats based on destinationId and reference
        query = """
            SELECT 
                SUM(value) AS total_value,
                COUNT(*) AS total_records,
                type
            FROM records
            WHERE destinationId = %s AND reference = %s
            GROUP BY destinationId, reference, type
        """
        params = [destinationId, reference]
        cursor.execute(query, params)
        records = cursor.fetchall()

        # Publish result to Redis channel
        message = json.dumps(records)
        redis.publish(channel, message)

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "inserted_record_id": recordId
        }), 201

    except Error as e:
        return jsonify({"error": str(e)}), 500

# Default route for basic health check
@app.route('/')
def default():
    return jsonify({"welcome": "smile"}), 200

# Insert a single record into the database
@app.route('/insert-records', methods=['POST'])
def insert_json():
    record = request.get_json()

    # Validate request payload
    if not record or not isinstance(record, dict):
        return jsonify({"error": "Expected a JSON object representing a single record."}), 400

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Build SQL INSERT dynamically from keys/values
        columns = ', '.join(f"`{col}`" for col in record.keys())
        placeholders = ', '.join(['%s'] * len(record))
        values = tuple(record.values())
        sql = f"INSERT INTO records ({columns}) VALUES ({placeholders})"

        cursor.execute(sql, values)
        conn.commit()

        cursor.close()
        conn.close()

        # Emit pub/sub event after successful insert
        return emit_record_created_notification(
            record.get("recordId"),
            record.get("destinationId"),
            record.get("reference")
        )

    except Error as e:
        return jsonify({"error": str(e)}), 500

# Retrieve records with optional filtering and aggregation
@app.route('/aggregated-records', methods=['GET'])
def get_aggregated_records():
    # Get optional query parameters
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    record_type = request.args.get('type')  # "positive" or "negative"

    filters = []
    params = []

    # Build dynamic WHERE clause
    if start_time:
        filters.append("time >= %s")
        params.append(start_time)
    if end_time:
        filters.append("time <= %s")
        params.append(end_time)
    if record_type in ["positive", "negative"]:
        filters.append("type = %s")
        params.append(record_type)

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        query = f"""
            SELECT * FROM records
            {where_clause}
            ORDER BY time DESC
        """
        cursor.execute(query, params)
        records = cursor.fetchall()

        # Group results by destinationId
        grouped = {}
        for record in records:
            dest_id = record['destinationId']
            if dest_id not in grouped:
                grouped[dest_id] = {
                    "records": [],
                    "totalValue": 0.0
                }
            grouped[dest_id]["records"].append(record)
            grouped[dest_id]["totalValue"] += float(record["value"]) if record["value"] else 0.0

        cursor.close()
        conn.close()

        return jsonify(grouped), 200

    except Error as e:
        return jsonify({"error": str(e)}), 500

# Entry point
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
