import unittest
from notification_graph.core import NotificationItem, NotificationGraph


class BasicTests(unittest.TestCase):

    def test0_create_item(self):
        item = NotificationItem(NotificationGraph())
        self.assertIsNotNone(item)
