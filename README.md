# 🧾 Transaction Processing Microservice – Documentation

## 📌 Overview

This microservice is designed to:

* Process structured data records from multiple sources
* Aggregate and serve them via query endpoints
* Emit notifications for downstream services
* Generate alerts for records exceeding a threshold

Built with:

* **Flask** (Python) – Web framework
* **MySQL** – Persistent storage
* **Redis** – Pub/Sub messaging system

This service is running on a AWS instance at:

[http://ec2-51-21-255-162.eu-north-1.compute.amazonaws.com:8000/](http://ec2-51-21-255-162.eu-north-1.compute.amazonaws.com:8000/)

The endpoints can be queried with any client like Postman.

---

## ✅ Requirements Coverage

### 1. **Consume input from multiple services with idempotency**

> *"The service should handle about 100,000 messages per hour efficiently. Implement idempotency to prevent duplicate processing..."*

#### 📦 Code Sections:

* **Endpoint:** `@app.route('/insert-records', methods=['POST'])`
* **Database Primary Key:** `recordId VARCHAR(255) PRIMARY KEY`

#### ✅ Explanation:

* Each incoming record has a unique `recordId`.
* MySQL enforces uniqueness via `PRIMARY KEY`.
* Attempted duplicates will fail insertion, ensuring **idempotency**.

* Response format example:

```json
{
    "inserted_record_id": "878bddkbb",
    "status": "success"
}
```

---

### 2. **Aggregation and querying support**

> *"Respond to queries for aggregation. The query and the response should support:*
>
> * *Start and end time filters*
> * *Type filter (positive/negative)*
> * *Grouping by `destinationId`*
> * *Total value per group"*

#### 📦 Code Section:

* `@app.route('/aggregated-records', methods=['GET'])`

#### ✅ Explanation:

* Supports optional query parameters:

  * `start_time`, `end_time`, `type`
* Uses dynamic SQL to filter based on parameters.
* Fields used in the `WHERE` clause are indexed to improve performance.
* Records are grouped by `destinationId`, each group includes:

  * Matching records
  * A running `totalValue` sum
* Request format example:

[http://ec2-51-21-255-162.eu-north-1.compute.amazonaws.com:8000/aggregated-records?destination_id=otherdest](http://ec2-51-21-255-162.eu-north-1.compute.amazonaws.com:8000/aggregated-records?destination_id=otherdest)

* Response format example:

```json
{
    "otherdest": {
        "records": [
            {
                "destinationId": "otherdest",
                "recordId": "bbb333",
                "reference": "someref123456",
                "sourceId": "somesource",
                "time": "Fri, 11 Jul 2025 17:19:45 GMT",
                "type": "positive",
                "unit": "euro",
                "value": "88.89"
            },
            {
                "destinationId": "otherdest",
                "recordId": "kkk777",
                "reference": "someref123456",
                "sourceId": "somesource",
                "time": "Fri, 11 Jul 2025 17:19:45 GMT",
                "type": "positive",
                "unit": "euro",
                "value": "75.88"
            }
        ],
        "totalValue": "164.77"
    }
}
```

---

### 3. **Emit messages per processed record**

> *"There should be one message for every record processed..."*

#### 📦 Code Section:

* `emit_record_created_notification()`
* Triggered inside `insert_json()` after successful insert.

#### ✅ Explanation:

* Publishes a JSON message to Redis channel: `record-stored-notification`
* Includes:

  * Aggregated stats: `total_value`, `total_records`, `type`
  * Filtered by `destinationId` and `reference`
  * Fields used in the `WHERE` clause are indexed to improve performance.
* Allows a notification service to subscribe and consume updates per record insertion.

---

### 4. **Emit alerts for high-value records**

> *"Emit messages to alerting service when a record’s value is above a configurable threshold"*

#### 📦 Code Section:

* Inside `emit_record_created_notification()`

```python
if value > threshold:
    redis.publish(high_channel, message)
```

#### ✅ Explanation:

* Configurable threshold: `threshold = 100.00`
* Publishes to Redis channel: `record-high-value-notification`
* Enables an alerting system to be triggered based on business rules.

---

## 📌 Routes Summary

| Method | Endpoint              | Description                         |
| ------ | --------------------- | ----------------------------------- |
| `GET`  | `/`                   | Health check route                  |
| `POST` | `/insert-records`     | Insert a single record              |
| `GET`  | `/aggregated-records` | Retrieve filtered & grouped records |

---

## 🧪 Future Enhancements

* Add json validation to avoid hitting DB layer for malformed records.
* Cache frequent aggregates in Redis for fast retrieval and also cache last N records to avoid duplicate messages from overloading DB.
* Add authentication/authorization to the endpoints.
* Configuration would be handled in a secure way, not hardcoded, that was just for simplicty.



