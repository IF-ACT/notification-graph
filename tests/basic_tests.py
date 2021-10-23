import unittest
from notification_graph.core import NotificationItem, NotificationType
from notification_graph.notification_behaviors import NotifySubscribers


class BasicTests(unittest.TestCase):

    def test0_create_item(self):
        item = NotificationItem()
        self.assertIsNotNone(item)
