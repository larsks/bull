from unittest import TestCase

from bull import mapper


class TestMapperTables(TestCase):
    '''Test class-based construction of device mapper tables.'''

    def test_empty_table(self):
        t = mapper.Table()
        assert str(t) == ''

    def test_zero(self):
        t = mapper.Zero()
        assert str(t) == 'zero'

    def test_linear(self):
        t = mapper.Linear('/dev/block')
        assert str(t) == 'linear /dev/block 0'

    def test_snapshot(self):
        t = mapper.Snapshot('/dev/block', '/dev/cow')
        assert str(t) == 'snapshot /dev/block /dev/cow N 16'

    def test_linear_segment(self):
        t = mapper.Segment(0, 2048, mapper.Linear('/dev/block'))
        assert str(t) == '0 2048 linear /dev/block 0'

    def test_populated_table(self):
        t = mapper.Table()
        t.append(mapper.Segment(0, 2048, mapper.Linear('/dev/block')))
        t.append(mapper.Segment(2048, 4096, mapper.Zero()))
        assert str(t) == ('0 2048 linear /dev/block 0\n'
                          '2048 4096 zero')

    def test_table_from_string(self):
        text = '\n'.join([
            '0 2048 linear /dev/block 0',
            '2048 4096 zero',
        ])

        t = mapper.Table.from_string(text)

        assert isinstance(t[0].target, mapper.Linear)
        assert isinstance(t[1].target, mapper.Zero)
