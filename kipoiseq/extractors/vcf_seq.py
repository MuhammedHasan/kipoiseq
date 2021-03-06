from collections import defaultdict
from tqdm import tqdm
from pybedtools import Interval
from pyfaidx import Sequence, complement
from kipoiseq.extractors import BaseExtractor, FastaStringExtractor
try:
    from cyvcf2 import VCF
except ImportError:
    VCF = object


def variant_to_id(variant):
    return "%s:%s:%s:['%s']" % (variant.CHROM, str(variant.POS),
                                variant.REF, variant.ALT[0])


__all__ = [
    'VariantSeqExtractor',
    'MultiSampleVCF',
    'SingleVariantVCFSeqExtractor',
    'SingleSeqVCFSeqExtractor'
]


class BaseQuery:
    # TODO: implement and, or functionity
    pass


class BaseVariantAllQuery(BaseQuery):
    """
    Closure for filtering variant-interval pairs.
    """

    # TODO: implement and, or functionity

    def __call__(self, variants, interval):
        raise NotImplementedError


class BaseVariantQuery(BaseQuery):
    """
    Closure for filtering variants.
    """

    # TODO: implement and, or functionity

    def __call__(self, variant):
        raise NotImplementedError


class BaseSampleAllQuery(BaseQuery):
    """
    Closure for filtering variant-interval pairs.
    """

    # TODO: implement and, or functionity

    def __call__(self, variants, interval, sample=None):
        raise NotImplementedError


class BaseSampleQuery(BaseQuery):
    """
    Closure for filtering variants.
    """

    # TODO: implement and, or functionity

    def __call__(self, variant, sample=None):
        raise NotImplementedError


class NumberVariantQuery(BaseVariantAllQuery):
    """
    Closure for variant query. Filter variants for interval
      if number of variants in given limits.
    """

    def __init__(self, max_num=float('inf'), min_num=0):
        # TODO: sample speficity
        self.max_num = max_num
        self.min_num = min_num

    def __call__(self, variants, interval):
        if self.max_num >= len(variants) >= self.min_num:
            return [True] * len(variants)
        else:
            return [False] * len(variants)


class VariantQueryable:

    def __init__(self, vcf, variants, progress=False):
        """
        Query object of variants.

        Args:
          vcf: cyvcf2.VCF objects.
          variants: iter of (variant, interval) tuples.
        """
        self.vcf = vcf
        if progress:
            self.variants = tqdm(variants)
        else:
            self.variants = variants

    def __iter__(self):
        for variants, interval in self.variants:
            yield from variants

    def filter(self, query):
        """
        Filters variant given conduction.

        Args:
          query: function which get a variant as input and filtered iter of
            variants.
        """
        raise NotImplementedError()

    def filter_all(self, query):
        """
        Filters variant given conduction.

        Args:
          query: function which get variants and an interval as input
            and filtered iter of variants.
        """
        return VariantQueryable(self.vcf, self._filter_all(query))

    def _filter_all(self, query):
        for variants, interval in self.variants:
            variants = list(variants)
            yield (v for v, cond in zip(variants, query(variants, interval))
                   if cond), interval

    def filter_by_num(self, max_num=float('inf'), min_num=0):
        """
        Filter variants for interval if number of variants in given limits.

        Args:
          max_num: allowed maximum number of variants.
          min_num: allowed minimum number of variants.

        Examples:
          To fetch variants if only single variant present in interval.

          >>> MultiSampleVCF(vcf_path) \
                .query_variants(intervals) \
                .filter_by_num_variant(max_num=1)
        """
        return self.filter_all(NumberVariantQuery(max_num, min_num))

    def to_vcf(self, path):
        """
        Parse query result as vcf file.

        Args:
          path: path of the file.
        """
        from cyvcf2 import Writer
        writer = Writer(path, self.vcf)
        for v in self:
            writer.write_record(v)


class SampleQueryable:
    def __init__(self, vcf, variants, progress=False):
        """
        Query object of variants.

        Args:
          vcf: cyvcf2.VCF objects.
          variants: iter of (Dict[sample, variants], interval) tuples.
        """
        self.vcf = vcf
        if progress:
            self.variants = tqdm(variants)
        else:
            self.variants = variants

    def __iter__(self):
        for sample_variants, interval in self.variants:
            yield sample_variants

    def filter(self, query):
        """
        Filters variant given conduction.

        Args:
          query: function which get a variant as input and filtered iter of
            variants.
        """
        # TODO: support sample query and variant query
        raise NotImplementedError()

    def filter_all(self, query):
        """
        Filters variant given conduction.

        Args:
          query: function which get variants, an interval, sample as input
            and filtered iter of variants.
        """
        # TODO: support sample query and variant query
        raise NotImplementedError()


class MultiSampleVCF(VCF):
    """
    Extended cyvcf2.VCF class for kipoiseq. It contains feature like
      querying variants or fetching variants with variant_id string.
    """

    def __init__(self, *args, **kwargs):
        from cyvcf2 import VCF
        super(MultiSampleVCF, self).__init__(*args, **kwargs)
        self.sample_mapping = dict(zip(self.samples, range(len(self.samples))))

    def _region(self, interval):
        return '%s:%d-%d' % (interval.chrom, interval.start, interval.end)

    def _has_variant(self, variant, sample_id):
        gt_type = variant.gt_types[self.sample_mapping[sample_id]]
        return self._has_variant_gt(gt_type)

    def _has_variant_gt(self, gt_type):
        return gt_type != 0 and gt_type != 2

    def fetch_variants(self, interval, sample_id=None):
        """
        Fetch variants for given interval from vcf file
          for sample if sample id is given.

        Args:
          interval List[pybedtools.Interval): pybedtools.Interval object
          sample_id (str, optional): sample id in vcf file.
        """
        for v in self(self._region(interval)):
            if sample_id is None or self._has_variant(v, sample_id):
                yield v

    def query_variants(self, intervals, sample_id=None, progress=False):
        """
        Fetch variants for given multi-intervals from vcf file
          for sample if sample id is given.

        Args:
          intervals (List[pybedtools.Interval]): list of Interval objects
          sample_id (str, optional): sample id in vcf file.

        Returns:
          VCFQueryable: queryable object whihc allow you to query the
            fetched variatns.

        Examples:
          To fetch variants if only single variant present in interval.

          >>> MultiSampleVCF(vcf_path) \
                .query_variants(intervals) \
                .filter_by_num_variant(max_num=1)
        """
        pairs = ((self.fetch_variants(i, sample_id=sample_id), i)
                 for i in intervals)
        return VariantQueryable(self, pairs, progress=progress)

    def get_variant_by_id(self, variant_id):
        """
        Returns variant from vcf file.

        Args:
          vcf: cyvcf2.VCF file
          variant_id: variant id hashed by `variant_to_id_str`

        Returns:
          Variant object.

        Examples:
          >>> MultiSampleVCF(vcf_path).get_variant_by_id("chr1:4:T:['C']")
        """
        chrom, pos, ref, alt = variant_id.split(':')
        pos = int(pos)
        alt = alt.split("'")[1]

        variants = self.fetch_variants(Interval(chrom, pos, pos))
        for v in variants:
            if v.REF == ref and v.ALT[0] == alt:
                return v
        raise KeyError('Variant %s not found in vcf file.' % variant_id)

    def get_samples(self, variant):
        """
        Fetchs sample names which have given variants

        Args:
          variant: variant object.

        Returns:
          Dict[str, int]: Dict of sample which have variant and gt as value.
        """
        return dict(filter(lambda x: self._has_variant_gt(x[1]),
                           zip(self.samples, variant.gt_types)))

    def fetch_samples_with_variants(self, intervals):
        """
        Fetchs variants for intervals and return it with samples.

        Args:
          interval (List[pybedtools.Interval]): Region of interest from which
            to query the sequence. 0-based

        Returns:
          Dict[str, Variant]: dict of samples as key and variants as values.
        """
        variant_sample = defaultdict(list)
        _variant_sample = defaultdict(set)

        for i in intervals:
            variants = self.fetch_variants(i)
            for v in variants:
                for s, gt in self.get_samples(v).items():
                    if variant_to_id(v) not in _variant_sample[s]:
                        variant_sample[s].append((v, gt))
                        _variant_sample[s].add(variant_to_id(v))

        return dict(variant_sample)

    def query_samples(self, intervals, progress=False):
        pairs = ((self.fetch_samples_with_variants([i]), i)
                 for i in intervals)
        return SampleQueryable(self, pairs, progress=progress)


class IntervalSeqBuilder(list):
    """
    String builder for `pyfaidx.Sequence` and `Interval` objects.
    """

    def restore(self, sequence):
        """
        Args:
          seq: `pyfaidx.Sequence` which convert all interval inside
            to `Seqeunce` objects.
        """
        for i, interval in enumerate(self):
            # interval.end can be bigger than interval.start
            interval_len = max(0, interval.end - interval.start)

            if type(self[i]) == Interval:
                start = interval.start - sequence.start
                end = start + interval_len
                self[i] = sequence[start: end]

    def _concat(self):
        for sequence in self:
            if type(sequence) != Sequence:
                raise TypeError('Intervals should be restored with `restore`'
                                ' method before calling concat method!')
            yield sequence.seq

    def concat(self):
        """
        Build the string from sequence objects.

        Returns:
          str: the final sequence.
        """
        return ''.join(self._concat())


class VariantSeqExtractor(BaseExtractor):

    def __init__(self, fasta_file):
        """
        Args:
          fasta_file: path to the fasta file (can be gzipped)
        """
        self.fasta = FastaStringExtractor(fasta_file, use_strand=True)

    def extract(self, interval, variants, anchor, fixed_len=True):
        """

        Args:
          interval: pybedtools.Interval Region of interest from
            which to query the sequence. 0-based
          variants List[cyvcf2.Variant]: variants overlapping the `interval`.
            can also be indels. 1-based
          anchor: absolution position w.r.t. the interval start. (0-based).
            E.g. for an interval of `chr1:10-20` the anchor of 10 denotes
            the point chr1:10 in the 0-based coordinate system.
          fixed_len: if True, the return sequence will have the same length
            as the `interval` (e.g. `interval.end - interval.start`)

        Returns:
          A single sequence (`str`) with all the variants applied.
        """
        # Preprocessing
        anchor = max(min(anchor, interval.end), interval.start)
        variant_pairs = self._variant_to_sequence(variants)

        # 1. Split variants overlapping with anchor
        # and interval start end if not fixed_len
        variant_pairs = self._split_overlapping(variant_pairs, anchor)

        if not fixed_len:
            variant_pairs = self._split_overlapping(
                variant_pairs, interval.start, which='right')
            variant_pairs = self._split_overlapping(
                variant_pairs, interval.end, which='left')

        variant_pairs = list(variant_pairs)

        # 2. split the variants into upstream and downstream
        # and sort the variants in each interval
        upstream_variants = sorted(
            filter(lambda x: x[0].start >= anchor, variant_pairs),
            key=lambda x: x[0].start)

        downstream_variants = sorted(
            filter(lambda x: x[0].start < anchor, variant_pairs),
            key=lambda x: x[0].start, reverse=True)

        # 3. Extend start and end position for deletions
        if fixed_len:
            istart, iend = self._updated_interval(
                interval, upstream_variants, downstream_variants)
        else:
            istart, iend = interval.start, interval.end

        # 4. Iterate from the anchor point outwards. At each
        # register the interval from which to take the reference sequence
        # as well as the interval for the variant
        down_sb = self._downstream_builder(
            downstream_variants, interval, anchor, istart)

        up_sb = self._upstream_builder(
            upstream_variants, interval, anchor, iend)

        # 5. fetch the sequence and restore intervals in builder
        seq = self._fetch(interval, istart, iend)
        up_sb.restore(seq)
        down_sb.restore(seq)

        # 6. Concate sequences from the upstream and downstream splits. Concat
        # upstream and downstream sequence. Cut to fix the length.
        down_str = down_sb.concat()
        up_str = up_sb.concat()

        if fixed_len:
            down_str, up_str = self._cut_to_fix_len(
                down_str, up_str, interval, anchor)

        seq = down_str + up_str

        if interval.strand == '-':
            seq = complement(seq)[::-1]

        return seq

    def _variant_to_sequence(self, variants):
        """
        Convert `cyvcf2.Variant` objects to `pyfaidx.Seqeunce` objects
        for reference and variants.
        """
        for v in variants:
            ref = Sequence(name=v.CHROM, seq=v.REF,
                           start=v.start, end=v.start + len(v.REF))
            # TO DO: consider alternative alleles.
            alt = Sequence(name=v.CHROM, seq=v.ALT[0],
                           start=v.start, end=v.start + len(v.ALT[0]))
            yield ref, alt

    def _split_overlapping(self, variant_pairs, anchor, which='both'):
        """
        Split the variants hitting the anchor into two
        """
        for ref, alt in variant_pairs:
            if ref.start < anchor < ref.end:
                mid = anchor - ref.start
                if which == 'left' or which == 'both':
                    yield ref[:mid], alt[:mid]
                if which == 'right' or which == 'both':
                    yield ref[mid:], alt[mid:]
            else:
                yield ref, alt

    def _updated_interval(self, interval, up_variants, down_variants):
        istart = interval.start
        iend = interval.end

        for ref, alt in up_variants:
            diff_len = len(alt) - len(ref)
            if diff_len < 0:
                iend -= diff_len

        for ref, alt in down_variants:
            diff_len = len(alt) - len(ref)
            if diff_len < 0:
                istart += diff_len

        return istart, iend

    def _downstream_builder(self, down_variants, interval, anchor, istart):
        down_sb = IntervalSeqBuilder()

        prev = anchor
        for ref, alt in down_variants:
            if ref.end <= istart:
                break
            down_sb.append(Interval(interval.chrom, ref.end, prev))
            down_sb.append(alt)
            prev = ref.start
        down_sb.append(Interval(interval.chrom, istart, prev))
        down_sb.reverse()

        return down_sb

    def _upstream_builder(self, up_variants, interval, anchor, iend):
        up_sb = IntervalSeqBuilder()

        prev = anchor
        for ref, alt in up_variants:
            if ref.start >= iend:
                break
            up_sb.append(Interval(interval.chrom, prev, ref.start))
            up_sb.append(alt)
            prev = ref.end
        up_sb.append(Interval(interval.chrom, prev, iend))

        return up_sb

    def _fetch(self, interval, istart, iend):
        seq = self.fasta.extract(Interval(interval.chrom, istart, iend))
        seq = Sequence(name=interval.chrom, seq=seq, start=istart, end=iend)
        return seq

    def _cut_to_fix_len(self,  down_str, up_str, interval, anchor):
        down_len = anchor - interval.start
        up_len = interval.end - anchor
        down_str = down_str[-down_len:] if down_len else ''
        up_str = up_str[: up_len] if up_len else ''
        return down_str, up_str


class BaseVCFSeqExtractor(BaseExtractor):
    """
    Base class to fetch sequence in which variants applied based
    on given vcf file.
    """

    def __init__(self, fasta_file, vcf_file):
        """
        Args:
          fasta_file: path to the fasta file (can be gzipped)
          vcf_file: path to the fasta file (need be bgzipped and indexed)
        """
        self.fasta_file = fasta_file
        self.vcf_file = vcf_file
        self.variant_extractor = VariantSeqExtractor(fasta_file)
        self.vcf = MultiSampleVCF(vcf_file)


class SingleVariantVCFSeqExtractor(BaseVCFSeqExtractor):
    """
    Fetch list of sequence in which each variant applied based
    on given vcf file.
    """

    def extract(self, interval, anchor=None, sample_id=None, fixed_len=True):
        for variant in self.vcf.fetch_variants(interval, sample_id):
            yield self.variant_extractor.extract(interval,
                                                 variants=[variant],
                                                 anchor=anchor,
                                                 fixed_len=fixed_len)


class SingleSeqVCFSeqExtractor(BaseVCFSeqExtractor):
    """
    Fetch sequence in which all variant applied based on given vcf file.
    """

    def extract(self, interval, anchor=None, sample_id=None, fixed_len=True):
        return self.variant_extractor.extract(
            interval, variants=self.vcf.fetch_variants(interval, sample_id),
            anchor=anchor, fixed_len=fixed_len)
