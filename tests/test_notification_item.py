import unittest
from notification_graph.core import NotificationItem


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

    def test3_tree(self):
        items = self.create_items(7)

        items[0].subscribe(items[1])
        items[0].subscribe(items[2])

        items[3].subscribe(items[4])
        items[4].subscribe(items[5])
        items[4].subscribe(items[6])

        self.assertTrue(items[0].graph.is_tree)
        self.assertTrue(items[0].is_head_of_tree)
        self.assertFalse(items[1].is_head_of_tree)
        self.assertTrue(items[3].graph.is_tree)

        items[1].subscribe(items[3])

        self.assertTrue(items[0].is_head_of_tree)

        items[2].subscribe(items[5])

        self.assertFalse(items[0].graph.is_tree)

    @staticmethod
    def create_items(count):
        return [NotificationItem(f'Item{i}') for i in range(count)]
