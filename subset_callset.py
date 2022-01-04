import hail as hl
import pprint
import logging

logger = logging.getLogger(__name__)


class MatrixTableSampleSetError(Exception):
    def __init__(self, message, missing_samples):
        super().__init__(message)
        self.missing_samples = missing_samples

def subset_samples_and_variants(mt, subset_path):
    """
    Subset the MatrixTable to the provided list of samples and to variants present in those samples
    :param mt: MatrixTable from VCF
    :param subset_path: Path to a file with a single column 's'
    :return: MatrixTable subsetted to list of samples
    """
    subset_ht = hl.import_table(subset_path, key='s')
    subset_count = subset_ht.count()
    anti_join_ht = subset_ht.anti_join(mt.cols())
    anti_join_ht_count = anti_join_ht.count()

    
    if anti_join_ht_count != 0:
        missing_samples = anti_join_ht.s.collect()
        raise MatrixTableSampleSetError(
            f'Only {subset_count-anti_join_ht_count} out of {subset_count} '
            'subsetting-table IDs matched IDs in the variant callset.\n'
            f'IDs that aren\'t in the callset: {missing_samples}\n'
            f'All callset sample IDs:{mt.s.collect()}', missing_samples
        )
	
    mt = mt.semi_join_cols(subset_ht)
    mt = mt.filter_rows(hl.agg.any(mt.GT.is_non_ref()))

    logger.info(f'Finished subsetting samples. Kept {subset_count} '
                f'out of {mt.count()} samples in vds')
    return mt

def remap_sample_ids(mt, remap_path):
    """
    Remap the MatrixTable's sample ID, 's', field to the sample ID used within seqr, 'seqr_id'
    If the sample 's' does not have a 'seqr_id' in the remap file, 's' becomes 'seqr_id'
    :param mt: MatrixTable from VCF
    :param remap_path: Path to a file with two columns 's' and 'seqr_id'
    :return: MatrixTable remapped and keyed to use seqr_id
    """
    remap_ht = hl.import_table(remap_path, key='s')
    missing_samples = remap_ht.anti_join(mt.cols()).collect()
    remap_count = remap_ht.count()

    if len(missing_samples) != 0:
        raise MatrixTableSampleSetError(
            f'Only {remap_ht.semi_join(mt.cols()).count()} out of {remap_count} '
            'remap IDs matched IDs in the variant callset.\n'
            f'IDs that aren\'t in the callset: {missing_samples}\n'
            f'All callset sample IDs:{mt.s.collect()}', missing_samples
        )

    mt = mt.annotate_cols(**remap_ht[mt.s])
    remap_expr = hl.cond(hl.is_missing(mt.seqr_id), mt.s, mt.seqr_id)
    mt = mt.annotate_cols(seqr_id=remap_expr, vcf_id=mt.s)
    mt = mt.key_cols_by(s=mt.seqr_id)
    logger.info(f'Remapped {remap_count} sample ids...')
    return mt


hl.init(master='spark://compute-m7c1-0-4.localdomain:7077')
mt = hl.read_matrix_table('/scratch/ch227850/Monkol/crdc_joint_called.mt')
#pprint.pprint(mt.count())

#mt = remap_sample_ids(mt, '/scratch/ch227850/Monkol/seqr_cohorts/beggs/beggs_sample_remap.tsv')
#mt = subset_samples_and_variants(mt,'/scratch/ch227850/Monkol/seqr_cohorts/beggs/vcf_beggs_subset_FINAL.txt')

#mt = remap_sample_ids(mt, '/scratch/ch227850/Monkol/seqr_cohorts/manton/mantongdc_sample_remap.tsv')
#mt = subset_samples_and_variants(mt,'/scratch/ch227850/Monkol/seqr_cohorts/manton/mantongdc_subset.txt')

mt = remap_sample_ids(mt, '/scratch/ch227850/Monkol/seqr_cohorts/dsd/hirschhorn_dsd_sample_remap.tsv')
mt = subset_samples_and_variants(mt,'/scratch/ch227850/Monkol/seqr_cohorts/dsd/hirschhorn_dsd_subset.tsv')

#pprint.pprint(mt.count())

#mt.write('/scratch/ch227850/Monkol/beggs.mt')
#mt.write('/scratch/ch227850/Monkol/mantongdc.mt')

mt.write('/scratch/ch227850/Monkol/hirschhorn_dsd.mt')














