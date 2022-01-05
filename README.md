# Seqr BCH Instance
This repo contains the configuration, notes and files to get [Seqr](https://github.com/broadinstitute/seqr) running on the BCH network (including HPC), which also uses EC2 instances. This also contains details on how to get [S3 and IGV to work](https://github.com/leklab/seqr_bch_instance/tree/main/s3_support) based on prior work by [Nick C.](https://github.com/nicklecompteBCH/seqr-bch-installation)


## Setting up VEP and Perl
Setting up Perl and required libraries is very annoying and doesn't work easily in a conda environment. In addition, the BCH E2 cluster and MGH PCC cluster nodes are not
running the same subset of libraries. The best work around at the moment is to install required Perl libraries in home directory and set as a PATH. The installation of Perl libraries does not work out of box in either clusters as things are missing. The working solution is to copy over the files needed.
```
# Copy over the following files into ~/perl5
tar xvf perl_libraries.tar.gz

# set PATH, for example
export PERL5LIB=$PERL5LIB:~/perl5:~/perl5/lib:~/perl5/lib/perl5/x86_64-linux-thread-multi:~/perl5/lib/perl5

```

## Setting up Hail/VEP annotation pipeline on HPC using slurm
```
# Setting up conda environment
conda env create -f hail_environment.yml

# Get the seqr/hail annotation pipeline
git clone https://github.com/broadinstitute/hail-elasticsearch-pipelines.git

# Get seqr hail tables used for annotation
# Files are currently in: 
gsutil -m cp -r gs://seqr-reference-data/GRCh37/all_reference_data/combined_reference_data_grch37.ht
gsutil -m cp -r gs://seqr-reference-data/GRCh38/all_reference_data/combined_reference_data_grch38.ht
gsutil -m cp -r gs://seqr-reference-data/GRCh37/clinvar/clinvar.GRCh37.ht
gsutil -m cp -r gs://seqr-reference-data/GRCh38/clinvar/clinvar.GRCh38.ht
gsutil -m cp -r gs://hail-common/references/grch38_to_grch37.over.chain.gz

# Setting up a SPARK cluster
git clone https://github.com/leklab/spark_on_slurm

```

## Running Hail/VEP annotation pipeline
```
# Activate conda environment
conda activate hail

# Start SPARK cluster. Eg. this will create a cluster with 6 nodes, 16 cpus/node (total of 6*16 = 96 workers) to run for 3h.
./create-spark-cluster.sh -n 6 -c 16 -t 3h

# Subset and rename samples
python subset_callset.py

# Annotate vcf file and export to Hail matrix table, for example
python seqr_loading.py SeqrVCFToMTTask --local-scheduler \
--source-paths source.vcf.gz \
--mt-path input.mt \
--genome-version 37 \
--sample-type WES \
--dont-validate \
--spark-master spark://node:7077 \
--dest-path output.mt \
--reference-ht-path combined_reference_data_grch37.ht \
--clinvar-ht-path clinvar.GRCh37.ht \
--grch38-to-grch37-ref-chain grch38_to_grch37.over.chain.gz \
--vep-config-json-path vep-GRCh37.json

# Upload data to Elastic Search server
python es_upload.py

```
