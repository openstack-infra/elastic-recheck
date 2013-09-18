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

    def test_ready(self):
        self.classifier._wait_till_ready('30043', '34','BLAH http://logs.openstack.org/43/30043/34/check/gate-tempest-devstack-vm-full/b852a33')

    def test_classify(self):
        bug_number = self.classifier.classify('43258', '13',
            ' blah http://logs.openstack.org/58/43258/13/check/gate-tempest-devstack-vm-neutron/55a7887')
        self.assertEqual(bug_number, '1211915')

    def test_url(self):
        url = self.classifier._prep_url('http://logs.openstack.org/13/46613/2/check/gate-tempest-devstack-vm-full/864bf44/console.html')
        self.assertEqual(url,
                         'http://logs.openstack.org/13/46613/2/check/gate-tempest-devstack-vm-full/864bf44')

