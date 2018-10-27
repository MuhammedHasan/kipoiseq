import os
import numpy as np
import pytest
from copy import deepcopy
from pybedtools import Interval
from kipoi.utils import override_default_kwargs
from kipoiseq.transforms.functional import one_hot_dna
from kipoiseq.dataloaders.sequence import IntervalSeqStringDl, IntervalSeqDl, parse_dtype, BedDataset


@pytest.fixture
def fasta_file():
    return "tests/data/sample.fasta"


@pytest.fixture
def intervals_file():
    return "tests/data/sample_intervals.bed"


# fasta_file = fasta_file()
# intervals_file = intervals_file()


def test_min_props():
    # minimal set of properties that need to be specified on the object
    min_set_props = ["output_schema", "type", "defined_as", "info", "args", "dependencies", "postprocessing",
                     "source", "source_dir"]

    for Dl in [IntervalSeqStringDl, IntervalSeqDl]:
        props = dir(Dl)
        assert all([el in props for el in min_set_props])


def test_parse_dtype():
    dtypes = {'int': int, 'string': str, 'float': float, 'bool': bool}
    assert all([parse_dtype(dt) == dtypes[dt] for dt in dtypes.keys()])
    assert all([parse_dtype(dt) == dt for dt in dtypes.values()])
    with pytest.raises(Exception):
        parse_dtype("int8")
    assert parse_dtype(None) is None


def test_fasta_based_dataset(intervals_file, fasta_file):
    # just test the functionality
    dl = IntervalSeqStringDl(intervals_file, fasta_file)
    ret_val = dl[0]
    assert isinstance(ret_val["inputs"], np.ndarray)
    assert ret_val["inputs"].shape == ()
    # # test with set wrong seqlen:
    # dl = IntervalSeqStringDl(intervals_file, fasta_file, required_seq_len=3)
    # with pytest.raises(Exception):
    #     dl[0]

    dl = IntervalSeqStringDl(intervals_file, fasta_file, label_dtype="string")
    ret_val = dl[0]
    assert isinstance(ret_val['targets'][0], np.str_)
    dl = IntervalSeqStringDl(intervals_file, fasta_file, label_dtype="int")
    ret_val = dl[0]
    assert isinstance(ret_val['targets'][0], np.int_)
    dl = IntervalSeqStringDl(intervals_file, fasta_file, label_dtype="bool")
    ret_val = dl[0]
    assert isinstance(ret_val['targets'][0], np.bool_)
    vals = dl.load_all()
    assert vals['inputs'][0] == 'GT'


def test_seq_dataset(intervals_file, fasta_file):
    dl = IntervalSeqDl(intervals_file, fasta_file)
    ret_val = dl[0]

    assert np.all(ret_val['inputs'] == one_hot_dna("GT"))
    assert isinstance(ret_val["inputs"], np.ndarray)
    assert ret_val["inputs"].shape == (2, 4)


# download example files
@pytest.mark.parametrize("cls", [IntervalSeqStringDl, IntervalSeqDl])
def test_examples_exist(cls):
    ex = cls.init_example()
    example_kwargs = cls.example_kwargs
    bed_fh = open(example_kwargs['intervals_file'], "r")
    bed_entries = len([el for el in bed_fh])
    bed_fh.close()

    dl_entries = 0
    for out in ex:
        dl_entries += 1
    assert dl_entries == len(ex)
    assert len(ex) == bed_entries


def test_output_schape():
    Dl = deepcopy(IntervalSeqDl)
    assert Dl.get_output_schema().inputs.shape == (None, 4)
    override_default_kwargs(Dl, {"auto_resize_len": 100})
    assert Dl.get_output_schema().inputs.shape == (100, 4)

    override_default_kwargs(Dl, {"auto_resize_len": 100, "dummy_axis": 1, "alphabet_axis": 2})
    assert Dl.get_output_schema().inputs.shape == (100, 1, 4)
    override_default_kwargs(Dl, {"auto_resize_len": 100, "dummy_axis": None, "alphabet_axis": 1})  # reset
    override_default_kwargs(Dl, {"auto_resize_len": 100, "dummy_axis": 2})
    assert Dl.get_output_schema().inputs.shape == (100, 4, 1)
    override_default_kwargs(Dl, {"auto_resize_len": 100, "dummy_axis": None, "alphabet_axis": 1})  # reset

    override_default_kwargs(Dl, {"auto_resize_len": 100, "alphabet": "ACGTD"})
    assert Dl.get_output_schema().inputs.shape == (100, 5)
    override_default_kwargs(Dl, {"auto_resize_len": 100, "alphabet": "ACGT"})  # reset

    override_default_kwargs(Dl, {"auto_resize_len": 160, "dummy_axis": 2, "alphabet_axis": 0})
    assert Dl.get_output_schema().inputs.shape == (4, 160, 1)

    override_default_kwargs(Dl, {"auto_resize_len": 160, "dummy_axis": 2, "alphabet_axis": 1})
    assert Dl.get_output_schema().inputs.shape == (160, 4, 1)
    targets = Dl.get_output_schema().targets
    assert targets.shape == (None,)

    override_default_kwargs(Dl, {"ignore_targets": True})
    assert Dl.get_output_schema().targets is None
    # reset back
    override_default_kwargs(Dl, {"ignore_targets": False})
    Dl.output_schema.targets = targets
