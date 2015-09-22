'''fasta2fastq.py - simulate reads from fasta
=====================================

:Author: Tom Smith
:Release: $Id$
:Date: |today|
:Tags: Sequences

Purpose
-------

Simulate illumina sequence reads from a fasta file. The number of
reads per entry is randomly selected from the range given. The primary
use case is expected to be the generation of simulation RNA-Seq reads

Available edit operations are:

paired
   generate paired-end reads (defaults to single end)

min-reads-per-entry
   the minimum number of reads to simulate for each fasta entry

max-reads-per-entry
   the maximum number of reads to simulate for each fasta entry

phred
   the sequencing error rate (phred scale)

format
   the format of the sequence qualities (+33 = Sanger)

insert-mean
   the mean insert length

insert-sd
   the standard deviation for the insert length

If generating paired end reads, the second outfile must be specified with:

fastq-out2


Usage
-----

Example::

   cat transcripts.fa | python fasta2fastq.py > simulation_reads.fastq

Type::

   python fasta2fastq.py --help

for command line help.

Command line options
---------------------

'''
import sys
import random
import numpy as np

import CGAT.Experiment as E
import CGAT.IOTools as IOTools

import CGAT.FastaIterator as FastaIterator


def addSeqErrors(read=None, error_rate=10):
    ''' add sequencing errors to a read.
    Error rates are Phred scaled, so 30 = 1/1000'''

    error_rate = 10**(error_rate/-10.0)

    errors_dict = {"G": ["C", "T", "A"],
                   "C": ["G", "T", "A"],
                   "T": ["C", "G", "A"],
                   "A": ["C", "T", "G"],
                   "N": ["C", "T", "G", "A"]}

    probs = np.random.rand(len(read))
    return "".join([base if prob > error_rate and base != "N"
                    else random.choice(errors_dict[base])
                    for prob, base in zip(probs, read)])


def reverseComp(seq):
    ''' return the reverse complement sequence '''

    comp = {"G": "C",
            "C": "G",
            "A": "T",
            "T": "A"}

    return "".join([comp[base] for base in seq[::-1]])


def generateRead(entry, read_length=50, error_rate=40, paired=False,
                 insert_mean=0, insert_sd=1):
    ''' generate a read (or read pair) at random from a fasta entry for
    the given read length with sequencing errors according to error
    rate'''

    if paired:

        position = "not_OK"

        while position != "OK":

            r1_start = random.randint(0, len(entry)-read_length)
            r2_start = (r1_start + read_length +
                        int(np.random.normal(insert_mean, insert_sd)))

            if ((r2_start <= len(entry) - read_length) and
                (r2_start >= r1_start)):

                position = "OK"

                read1 = entry[r1_start: r1_start+read_length]
                read2 = reverseComp(
                    entry[r2_start: r2_start+read_length])

                final_read1 = addSeqErrors(read1, error_rate)
                final_read2 = addSeqErrors(read2, error_rate)

                return final_read1, final_read2

    else:
        start = random.randint(0, len(entry)-read_length)
        read = entry[start:start+read_length]

        final_read = addSeqErrors(read, error_rate)

        return final_read


# ------------------------------------------------------------


def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = E.OptionParser(version="%prog version",
                            usage=globals()["__doc__"])

    parser.add_option(
        "--format", dest="q_format", type="int",
        help="sequence quality format, e.g 33 = +33/Sanger"
        "[default=%default].")

    parser.add_option(
        "--paired", dest="paired", action="store_true",
        help="generate paired end reads [default = %default].")

    parser.add_option(
        "--insert-mean", dest="insert_mean", type="float",
        help="mean insert length [default = %default].")

    parser.add_option(
        "--insert-sd", dest="insert_sd", type="float",
        help="insert length standard deviation [default = %default].")

    parser.add_option(
        "--min-reads-per-entry", dest="min_reads_per_entry", type="int",
        help="minimum number of reads/read pairs per fasta entry "
        "[default = %default].")

    parser.add_option(
        "--max-reads-per-entry", dest="max_reads_per_entry", type="int",
        help="maximum number of reads/read pairs per fasta entry "
        "[default = %default].")

    parser.add_option(
        "--read-length", dest="read_length", type="int",
        help="read length [default = %default].")

    parser.add_option(
        "--phred", dest="phred", type="int",
        help="phred quality score [default = %default].")

    parser.add_option(
        "--output-counts", dest="output_counts", type="string",
        help="name for counts outfile [default=%default].")

    parser.add_option(
        "--output-fastq2-out", dest="fastq2_out", type="string",
        help="filename for second fastq outfile [default=%default].")

    parser.set_defaults(
        q_format=33,
        paired=False,
        insert_mean=0,
        insert_sd=1,
        min_reads_per_entry=1,
        max_reads_per_entry=1,
        read_length=50,
        fastq2_out=None,
        output_counts=None,
        phred=30
    )

    (options, args) = E.Start(parser)

    if options.paired:
        assert options.fastq2_out, ("must specify a second fastq outfile for "
                                    "paired end (--output-fastq2-out)")
        outf2 = IOTools.openFile(options.fastq2_out, "w")

    # the sequence quality string will always be the same so define here
    sequence_quality = chr(options.q_format + options.phred)
    qual = "".join([sequence_quality] * options.read_length)

    iterator = FastaIterator.FastaIterator(options.stdin)

    # set a cut off of twice the read/pair length for short entries
    if options.paired:
        minimum_entry_length = (
            2 * (options.read_length * 2) + options.insert_mean)
    else:
        minimum_entry_length = 2 * options.read_length

    counts_out = IOTools.openFile(options.output_counts, "w")
    counts_out.write("%s\n" % "\t".join(("id", "read_count")))

    skipped = 0
    not_skipped = 0

    for entry in iterator:

        # reject short fasta entries
        if len(entry.sequence) < minimum_entry_length:
            E.info("skipping short transcript: %s length=%i"
                   % (entry.title, len(entry.sequence)))
            skipped += 1
            continue

        else:
            not_skipped += 1

        entry.sequence = entry.sequence.upper()
        entry_id = entry.title.split()[0]

        count = random.randint(options.min_reads_per_entry,
                               options.max_reads_per_entry + 1)

        counts_out.write("%s\n" % "\t".join(map(str, (entry_id, count))))

        for i in range(0, count + 1):

            read = generateRead(entry=entry.sequence,
                                read_length=options.read_length,
                                error_rate=options.phred,
                                paired=options.paired,
                                insert_mean=options.insert_mean,
                                insert_sd=options.insert_sd)

            if options.paired:

                r1, r2 = read

                h1 = "@%s_%i/1" % (entry_id, i)
                h2 = "@%s_%i/2" % (entry_id, i)

                options.stdout.write("\n".join((h1, r1, "+", qual)) + "\n")
                outf2.write("\n".join((h2, r2, "+", qual)) + "\n")

            else:

                h = "@%s_%i/1" % (entry_id, i)

                options.stdout.write("\n".join((h, read, "+", qual)) + "\n")

    if options.paired:
        outf2.close()

    counts_out.close()

    E.info("Reads simulated for %i fasta entries, %i entries skipped"
           % (not_skipped, skipped))

    E.Stop()

if __name__ == "__main__":
    sys.exit(main(sys.argv))
