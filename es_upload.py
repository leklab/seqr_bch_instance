import hail as hl
import math
from hail_scripts.elasticsearch.hail_elasticsearch_client import HailElasticsearchClient


def export_table_to_elasticsearch(es, table, num_shards, index_name):

    es.export_table_to_elasticsearch(table,
                                           index_name=index_name,
                                           func_to_run_after_index_exists=None,
                                           elasticsearch_mapping_id="docId",
                                           num_shards=num_shards,
                                           write_null_values=True)

def elasticsearch_row(ds):
    """
    Prepares the mt to export using ElasticsearchClient V02.
    - Flattens nested structs
    - drops locus and alleles key
    TODO:
    - Call validate
    - when all annotations are here, whitelist fields to send instead of blacklisting.
    :return:
    """

    # Converts a mt to the row equivalent.
    if isinstance(ds, hl.MatrixTable):
        ds = ds.rows()

    # Converts nested structs into one field, e.g. {a: {b: 1}} => a.b: 1
    table = ds.drop('vep').flatten()

    # When flattening, the table is unkeyed, which causes problems because our locus and alleles should not
    # be normal fields. We can also re-key, but I believe this is computational?
    table = table.drop(table.locus, table.alleles)


    return table


def mt_num_shards(mt):
    # The greater of the user specified min shards and calculated based on the variants and samples
    denominator = 1.4*10**9
    calculated_num_shards = math.ceil((mt.count_rows() * mt.count_cols())/denominator)

    #return max(self.es_index_min_num_shards, calculated_num_shards)
    return calculated_num_shards




es = HailElasticsearchClient(host='172.31.45.128')

mt = hl.read_matrix_table('/data/seqr_beggs.mt')
row_table = elasticsearch_row(mt)
es_shards = mt_num_shards(mt)

export_table_to_elasticsearch(es, row_table, es_shards, 'beggs_test_20211103')


