"""Test the main config logic."""
import io
import uuid

from srctools import Property, bool_as_int
import pytest

import config


class DataSingle(config.Data, conf_name='TestName', version=2, uses_id=False):
    """Simple data type, not using IDs."""
    def __init__(self, value: str, triple: str) -> None:
        self.value = value
        self.triple = triple

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DataSingle):
            return self.value == other.value and self.triple == other.triple
        return NotImplemented

    @classmethod
    def parse_kv1(cls, data: Property, version: int) -> 'DataSingle':
        """Parse keyvalues."""
        if version == 2:
            triple_str = data['triple']
            if triple_str in {"a", "b", "c"}:
                triple = triple_str
            else:
                raise ValueError('Illegal triple.', triple_str)
        elif version == 1:
            triple = "b" if data.bool('is_bee') else "a"
        else:
            raise ValueError('Unknown version', version)
        return DataSingle(data['value'], triple)

    def export_kv1(self) -> Property:
        """Write out KV1 data."""
        return Property('TestData', [
            Property('value', self.value),
            Property('triple', self.triple),
        ])


def test_basic_store() -> None:
    """Test storing config values."""
    spec = config.ConfigSpec(None)
    spec.register(DataSingle)

    data_1 = DataSingle("value_1", "b")
    data_2 = DataSingle("value_2", "b")
    data_3 = DataSingle("value_3", "a")

    with pytest.raises(KeyError):
        spec.get_cur_conf(DataSingle)
    assert spec.get_cur_conf(DataSingle, default=data_2) is data_2

    spec.store_conf(data_1)
    assert spec.get_cur_conf(DataSingle) is data_1
    assert spec.get_cur_conf(DataSingle, default=data_2) is data_1

    spec.store_conf(data_3)
    assert spec.get_cur_conf(DataSingle) is data_3
    assert spec.get_cur_conf(DataSingle, default=data_1) is data_3


@pytest.mark.parametrize('triple', ['a', 'b'])
@pytest.mark.parametrize('value', [
    'testing testing',
    'multi\nline\nstring',
])
def test_parse_kv1_upgrades(value: str, triple: str) -> None:
    """Test parsing Keyvalues1 data, and upgrading old versions."""
    spec = config.ConfigSpec(None)
    spec.register(DataSingle)

    props = Property.root(
        Property('version', '1'),
        Property('TestName', [
            Property('_version', '1'),
            Property('value', value),
            Property('is_bee', bool_as_int(triple == 'b')),
        ])
    )
    conf, upgraded = spec.parse_kv1(props)
    assert upgraded
    assert conf == {DataSingle: {'': DataSingle(value, triple)}}

    props = Property.root(
        Property('version', '1'),
        Property('TestName', [
            Property('_version', '2'),
            Property('value', value),
            Property('triple', triple),
        ])
    )
    conf, upgraded = spec.parse_kv1(props)
    assert not upgraded
    assert conf == {DataSingle: {'': DataSingle(value, triple)}}


@pytest.mark.parametrize('triple', ['a', 'b', 'c'])
@pytest.mark.parametrize('value', ['val1', 'val2'])
def test_export_kv1_regress(value: str, triple: str, file_regression) -> None:
    """Test exporting KV1 produces the same result."""
    spec = config.ConfigSpec(None)
    spec.register(DataSingle)

    conf = config.Config({
        DataSingle: {'': DataSingle(value, triple)}
    })
    props = Property.root(*spec.build_kv1(conf))

    buf = io.StringIO()
    buf.writelines(props.export())

    file_regression.check(
        buf.getvalue(),
        basename=f'export_noid_{triple}_{value}', extension='.vdf',
    )


@pytest.mark.parametrize('triple', ['a', 'b', 'c'])
@pytest.mark.parametrize('value', ['val1', 'val2'])
def test_export_dmx_regress(value: str, triple: str, file_regression) -> None:
    """Test exporting DMX produces the same result."""
    spec = config.ConfigSpec(None)
    spec.register(DataSingle)

    conf = config.Config({
        DataSingle: {'': DataSingle(value, triple)}
    })
    elem = spec.build_dmx(conf)
    # The root UUID is always present, override to some fixed value so we can compare.
    elem.uuid = uuid.UUID(hex='5f6c487e-1365-49e6-80d4-effe1abe1701')

    buf = io.BytesIO()
    elem.export_kv2(buf, 'BEEConfig', 1, unicode='format', cull_uuid=True)
    file_regression.check(
        buf.getvalue().decode().replace('\r\n', '\n'),
        basename=f'export_noid_{triple}_{value}', extension='.dmx',
    )
