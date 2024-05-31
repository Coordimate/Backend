import datetime

from firebase_admin import messaging


def notify_single_user(fcm_token, title, body):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        android=messaging.AndroidConfig(
            ttl=datetime.timedelta(seconds=3600),
            priority="normal",
            notification=messaging.AndroidNotification(
                icon="stock_ticker_update", color="#3d5a80"
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(badge=42),
            ),
        ),
        # Use topic to send messages to all subscribers of a topic
        # topic='industry-tech',
        # Use token to target a specific user
        token=fcm_token,
    )
    response = messaging.send(message)
    print(response)
