import testtools
import elasticRecheck


class TestClassifier(testtools.TestCase):

    def setUp(self):
        super(TestClassifier, self).setUp()
        self.classifier = elasticRecheck.Classifier()

    def test_read_qeuries_file(self):
        self.assertNotEqual(self.classifier.queries, None)

    def test_elasticSearch(self):
        self.classifier.test()
        self.classifier.last_failures()
        #self.assertFalse(True)

    def test_classify(self):
        bug_number = self.classifier.classify('46581', '1')
        self.assertEqual(bug_number, '1211915')

