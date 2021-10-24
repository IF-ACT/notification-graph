import unittest
from notification_graph.core import NotificationItem, NotificationType
from notification_graph.notification_behaviors import NotifySubscribers


class BasicTests(unittest.TestCase):

    def test0_create_item(self):
        item = NotificationItem()
        self.assertIsNotNone(item)

    def test1_detect_circle(self):
        item0 = NotificationItem()
        item1 = NotificationItem()
        item2 = NotificationItem()

        item0.subscribe(item1)
        item1.subscribe(item2)
        self.assertRaises(AssertionError, item2.subscribe, item0)

    def test2_merge_graphs(self):
        item0 = NotificationItem()
        item1 = NotificationItem()
        item2 = NotificationItem()
        item3 = NotificationItem()

        item0.subscribe(item1)
        item2.subscribe(item3)
        item1.subscribe(item3)

        self.assertIs(item0.graph, item1.graph)
        self.assertIs(item0.graph, item2.graph)
