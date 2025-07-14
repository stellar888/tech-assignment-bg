import unittest
from unittest.mock import patch, MagicMock
from app import app, threshold
import json
import datetime

class TestTransactionService(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        self.headers = {'Content-Type': 'application/json'}

    @patch('app.mysql.connector.connect')
    def test_health_check(self, mock_connect):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"welcome": "smile"})

    @patch('app.mysql.connector.connect')
    @patch('app.redis.publish')
    def test_insert_record_success_and_pubsub(self, mock_redis_publish, mock_mysql_connect):
        # Mock MySQL connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_mysql_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [[100, 1, "positive"]]

        test_record = {
            "recordId": "878bddkbb",
            "time": "2025-07-11 17:19:45",
            "sourceId": "somesource",
            "destinationId": "deeestination",
            "type": "positive",
            "value": 55,
            "unit": "euro",
            "reference": "dsfdfkjl23j4lk2j34"
        }

        response = self.client.post('/insert-records', data=json.dumps(test_record), headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertIn("inserted_record_id", response.get_json())
        self.assertTrue(mock_redis_publish.called)

    @patch('app.mysql.connector.connect')
    def test_insert_record_invalid_json(self, mock_mysql_connect):
        response = self.client.post('/insert-records', data="not-json", headers=self.headers)
        self.assertEqual(response.status_code, 400)

    @patch('app.mysql.connector.connect')
    def test_get_aggregated_records_with_filters(self, mock_mysql_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_mysql_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'recordId': '34343434', 
                'time': datetime.datetime(2025, 7, 11, 17, 19, 45), 
                'sourceId': 'somesource', 
                'destinationId': 'otherdest', 
                'type': 'positive', 
                'value': 55.8, 
                'unit': 'euro', 
                'reference': 'dsfdfkjl23j4lk2j34'
            }, 
            {
                'recordId': 'sdfdsddddfsdfd', 
                'time': datetime.datetime(2025, 7, 11, 17, 19, 45), 
                'sourceId': 'somesource', 
                'destinationId': 'otherdest', 
                'type': 'positive', 
                'value': 55.8, 
                'unit': 'euro', 
                'reference': 'dsfdfkjl23j4lk2j34'
            }
        ]

        response = self.client.get('/aggregated-records?type=positive&destination_id=otherdest')
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("otherdest", data)
        self.assertEqual(data["otherdest"]["totalValue"], 111.6)

    @patch('app.mysql.connector.connect')
    @patch('app.redis.publish')
    def test_high_value_alert_triggered(self, mock_redis_publish, mock_mysql_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_mysql_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [[150, 1, "positive"]]

        high_value_record = {
            "recordId": "878bddkbb",
            "time": "2025-07-11 17:19:45",
            "sourceId": "somesource",
            "destinationId": "deeestination",
            "type": "positive",
            "value": threshold + 50,  # triggers alert
            "unit": "euro",
            "reference": "dsfdfkjl23j4lk2j34"
        }

        response = self.client.post('/insert-records', data=json.dumps(high_value_record), headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(mock_redis_publish.called)

        # Expect two publishes: one for normal channel, one for high alert
        self.assertEqual(mock_redis_publish.call_count, 2)

    @patch('app.mysql.connector.connect')
    def test_idempotent_insert_fails_duplicate(self, mock_mysql_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_mysql_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate duplicate entry exception
        from mysql.connector import IntegrityError
        mock_cursor.execute.side_effect = IntegrityError("Duplicate entry")

        duplicate_record = {
            "recordId": "878bddkbb",
            "time": "2025-07-11 17:19:45",
            "sourceId": "somesource",
            "destinationId": "deeestination",
            "type": "positive",
            "value": 55,
            "unit": "euro",
            "reference": "dsfdfkjl23j4lk2j34"
        }

        response = self.client.post('/insert-records', data=json.dumps(duplicate_record), headers=self.headers)
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.get_json())

if __name__ == '__main__':
    unittest.main()
