# coding=utf-8
# Copyright 2018 The Google AI Language Team Authors and The HugginFace Inc. team.
# Copyright (c) 2018, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""BERT finetuning runner."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import csv
import os
import logging
import argparse
import random
from tqdm import tqdm, trange

import numpy as np
import torch
from torch.utils.data import TensorDataset, DataLoader, RandomSampler, SequentialSampler
from torch.utils.data.distributed import DistributedSampler

import metrics
from BERT.tokenization import BertTokenizer
from BERT.modeling import BertForFullSequenceRelevance
from BERT.optimization import BertAdam
from BERT.file_utils import PYTORCH_PRETRAINED_BERT_CACHE

logging.basicConfig(format = '%(asctime)s - %(levelname)s - %(name)s -   %(message)s',
                    datefmt = '%m/%d/%Y %H:%M:%S',
                    level = logging.INFO)
logger = logging.getLogger(__name__)


class InputExample(object):
    """A single training/test example for simple sequence classification."""

    def __init__(self, guid, text_a, text_b=None, label=None):
        """Constructs a InputExample.

        Args:
            guid: Unique id for the example.
            text_a: string. The untokenized text of the first sequence. For single
            sequence tasks, only this sequence must be specified.
            text_b: (Optional) string. The untokenized text of the second sequence.
            Only must be specified for sequence pair tasks.
            label: (Optional) string. The label of the example. This should be
            specified for train and dev examples, but not for test examples.
        """
        self.guid = guid
        self.text_a = text_a
        self.text_b = text_b
        self.label = label


class InputFeatures(object):
    """A single set of features of data."""

    def __init__(self, input_ids, input_mask, segment_ids, label_id):
        self.input_ids = input_ids
        self.input_mask = input_mask
        self.segment_ids = segment_ids
        self.label_id = label_id

class RelevanceFeatures(object):
    """A single set of features of relevance data."""

    def __init__(self, query_ids, psg_ids, query_mask, psg_mask, query_segment_ids, psg_segment_ids, label_id):
        self.query_ids = query_ids
        self.psg_ids = psg_ids
        self.query_mask = query_mask
        self.psg_mask = psg_mask
        self.query_segment_ids = query_segment_ids
        self.psg_segment_ids = psg_segment_ids
        self.label_id = label_id

class DataProcessor(object):
    """Base class for data converters for sequence classification data sets."""

    def get_train_examples(self, data_dir):
        """Gets a collection of `InputExample`s for the train set."""
        raise NotImplementedError()

    def get_dev_examples(self, data_dir):
        """Gets a collection of `InputExample`s for the dev set."""
        raise NotImplementedError()

    def get_test_examples(self, data_dir):
        """Gets a collection of `InputExample`s for the test set."""
        raise NotImplementedError()

    def get_labels(self):
        """Gets the list of labels for this data set."""
        raise NotImplementedError()

    @classmethod
    def _read_tsv(cls, input_file, quotechar=None):
        """Reads a tab separated value file."""
        with open(input_file, "r", encoding='utf-8') as f:
            reader = csv.reader(f, delimiter="\t", quotechar=quotechar)
            lines = []
            for line in reader:
                lines.append(line)
            return lines


class MrpcProcessor(DataProcessor):
    """Processor for the MRPC data set (GLUE version)."""

    def get_train_examples(self, data_dir):
        """See base class."""
        logger.info("LOOKING AT {}".format(os.path.join(data_dir, "train.tsv")))
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "train.tsv")), "train")

    def get_dev_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "dev.tsv")), "dev")

    def get_test_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "test.tsv")), "test")

    def get_labels(self):
        """See base class."""
        return ["0", "1"]

    def _create_examples(self, lines, set_type):
        """Creates examples for the training and dev sets."""
        examples = []
        for (i, line) in enumerate(lines):
            if i == 0:
                continue
            guid = "%s-%s" % (set_type, i)
            text_a = line[3]
            text_b = line[4]
            label = line[0]
            examples.append(
                InputExample(guid=guid, text_a=text_a, text_b=text_b, label=label))
        return examples


class MnliProcessor(DataProcessor):
    """Processor for the MultiNLI data set (GLUE version)."""

    def get_train_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "train.tsv")), "train")

    def get_dev_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "dev_matched.tsv")), "dev_matched")

    def get_test_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "test.tsv")), "test")

    def get_labels(self):
        """See base class."""
        return ["contradiction", "entailment", "neutral"]

    def _create_examples(self, lines, set_type):
        """Creates examples for the training and dev sets."""
        examples = []
        for (i, line) in enumerate(lines):
            if i == 0:
                continue
            guid = "%s-%s" % (set_type, line[0])
            text_a = line[8]
            text_b = line[9]
            label = line[-1]
            examples.append(
                InputExample(guid=guid, text_a=text_a, text_b=text_b, label=label))
        return examples


class ColaProcessor(DataProcessor):
    """Processor for the CoLA data set (GLUE version)."""

    def get_train_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "train.tsv")), "train")

    def get_dev_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "dev.tsv")), "dev")

    def get_test_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "test.tsv")), "test")

    def get_labels(self):
        """See base class."""
        return ["0", "1"]

    def _create_examples(self, lines, set_type):
        """Creates examples for the training and dev sets."""
        examples = []
        for (i, line) in enumerate(lines):
            guid = "%s-%s" % (set_type, i)
            text_a = line[3]
            label = line[1]
            examples.append(
                InputExample(guid=guid, text_a=text_a, text_b=None, label=label))
        return examples


class TextQnA(DataProcessor):
    """Processor for the TextQnA format which is a classification problem. where 1st column is query, 2nd is passage, 3rd is binary label."""
    
    def get_train_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "train.tsv")), "train")

    def get_dev_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "dev.tsv")), "dev")

    def get_test_examples(self, data_dir):
        """See base class."""
        return self._create_examples(self._read_tsv(os.path.join(data_dir, "test.tsv")), "test")

    def get_labels(self):
        """See base class."""
        return ["0", "1"]

    def _create_examples(self, lines, set_type):
        """Creates examples for the training and dev sets."""
        examples = []
        for (i, line) in enumerate(lines):
            guid = "%s-%s" % (set_type, i)
            text_a = line[0]
            text_b = line[1]
            label = line[2]
            examples.append(InputExample(guid=guid, text_a=text_a, text_b=text_b, label=label))
        return examples

def convert_examples_to_features(examples, label_list, max_seq_length, tokenizer):
    """Loads a data file into a list of `InputBatch`s."""

    label_map = {label : i for i, label in enumerate(label_list)}

    features = []
    for (ex_index, example) in enumerate(examples):
        tokens_a = tokenizer.tokenize(example.text_a)

        tokens_b = None
        if example.text_b:
            tokens_b = tokenizer.tokenize(example.text_b)
            # Modifies `tokens_a` and `tokens_b` in place so that the total
            # length is less than the specified length.
            # Account for [CLS], [SEP], [SEP] with "- 3"
            _truncate_seq_pair(tokens_a, tokens_b, max_seq_length - 3)
        else:
            # Account for [CLS] and [SEP] with "- 2"
            if len(tokens_a) > max_seq_length - 2:
                tokens_a = tokens_a[:(max_seq_length - 2)]

        # The convention in BERT is:
        # (a) For sequence pairs:
        #  tokens:   [CLS] is this jack ##son ##ville ? [SEP] no it is not . [SEP]
        #  type_ids: 0   0  0    0    0     0       0 0    1  1  1  1   1 1
        # (b) For single sequences:
        #  tokens:   [CLS] the dog is hairy . [SEP]
        #  type_ids: 0   0   0   0  0     0 0
        #
        # Where "type_ids" are used to indicate whether this is the first
        # sequence or the second sequence. The embedding vectors for `type=0` and
        # `type=1` were learned during pre-training and are added to the wordpiece
        # embedding vector (and position vector). This is not *strictly* necessary
        # since the [SEP] token unambigiously separates the sequences, but it makes
        # it easier for the model to learn the concept of sequences.
        #
        # For classification tasks, the first vector (corresponding to [CLS]) is
        # used as as the "sentence vector". Note that this only makes sense because
        # the entire model is fine-tuned.
        tokens = ["[CLS]"] + tokens_a + ["[SEP]"]
        segment_ids = [0] * len(tokens)

        if tokens_b:
            tokens += tokens_b + ["[SEP]"]
            segment_ids += [1] * (len(tokens_b) + 1)

        input_ids = tokenizer.convert_tokens_to_ids(tokens)

        # The mask has 1 for real tokens and 0 for padding tokens. Only real
        # tokens are attended to.
        input_mask = [1] * len(input_ids)

        # Zero-pad up to the sequence length.
        padding = [0] * (max_seq_length - len(input_ids))
        input_ids += padding
        input_mask += padding
        segment_ids += padding

        assert len(input_ids) == max_seq_length
        assert len(input_mask) == max_seq_length
        assert len(segment_ids) == max_seq_length

        label_id = label_map[example.label]
        if ex_index < 5:
            logger.info("*** Example ***")
            logger.info("guid: %s" % (example.guid))
            logger.info("tokens: %s" % " ".join(
                    [str(x) for x in tokens]))
            logger.info("input_ids: %s" % " ".join([str(x) for x in input_ids]))
            logger.info("input_mask: %s" % " ".join([str(x) for x in input_mask]))
            logger.info(
                    "segment_ids: %s" % " ".join([str(x) for x in segment_ids]))
            logger.info("label: %s (id = %d)" % (example.label, label_id))

        features.append(
                InputFeatures(input_ids=input_ids,
                              input_mask=input_mask,
                              segment_ids=segment_ids,
                              label_id=label_id))
    return features

def convert_examples_to_relevance_features(examples, label_list, max_seq_length, tokenizer):
    """Loads a data file into a list of `InputBatch`s."""

    label_map = {label : i for i, label in enumerate(label_list)}

    features = []
    for (ex_index, example) in enumerate(examples):
        
        tokens_a = tokenizer.tokenize(example.text_a)
        if len(tokens_a) > max_seq_length - 2:
            tokens_a = tokens_a[:(max_seq_length - 2)]

        tokens_b = tokenizer.tokenize(example.text_b)
        if len(tokens_b) > max_seq_length - 2:
            tokens_b = tokens_b[:(max_seq_length - 2)]

        tokens_1 = ["[CLS]"] + tokens_a + ["[SEP]"]
        query_segment_ids = [0] * len(tokens_1)

        tokens_2 = ["[CLS]"] + tokens_b + ["[SEP]"]
        psg_segment_ids = [0] * len(tokens_2)

        query_ids = tokenizer.convert_tokens_to_ids(tokens_1)
        psg_ids = tokenizer.convert_tokens_to_ids(tokens_2)

        # The mask has 1 for real tokens and 0 for padding tokens. Only real
        # tokens are attended to.
        query_mask = [1] * len(query_ids)
        psg_mask = [1] * len(psg_ids)

        # Zero-pad up to the sequence length.
        query_padding = [0] * (max_seq_length - len(query_ids))
        psg_padding = [0] * (max_seq_length - len(psg_ids))

        query_ids += query_padding
        query_mask += query_padding
        query_segment_ids += query_padding

        psg_ids += psg_padding
        psg_mask += psg_padding
        psg_segment_ids += psg_padding
        
        assert len(query_ids) == max_seq_length
        assert len(query_mask) == max_seq_length
        assert len(query_segment_ids) == max_seq_length
        assert len(psg_ids) == max_seq_length
        assert len(psg_mask) == max_seq_length
        assert len(psg_segment_ids) == max_seq_length

        label_id = label_map[example.label]
        if ex_index < 5:
            logger.info("*** Example ***")
            logger.info("guid: %s" % (example.guid))
            logger.info("query tokens: %s" % " ".join([str(x) for x in tokens_1]))
            logger.info("passage tokens: %s" % " ".join([str(x) for x in tokens_2]))
            logger.info("query_ids: %s" % " ".join([str(x) for x in query_ids]))
            logger.info("passage_ids: %s" % " ".join([str(x) for x in psg_ids]))
            logger.info("query_mask: %s" % " ".join([str(x) for x in query_mask]))
            logger.info("passage_mask: %s" % " ".join([str(x) for x in psg_mask]))
            logger.info("query_segment_ids: %s" % " ".join([str(x) for x in query_segment_ids]))
            logger.info("psg_segment_ids: %s" % " ".join([str(x) for x in psg_segment_ids]))
            logger.info("label: %s (id = %d)" % (example.label, label_id))

        features.append(
            RelevanceFeatures(query_ids=query_ids, psg_ids=psg_ids, query_mask=query_mask, psg_mask=psg_mask, query_segment_ids=query_segment_ids, psg_segment_ids=psg_segment_ids, label_id=label_id)
        )

    return features

def _truncate_seq_pair(tokens_a, tokens_b, max_length):
    """Truncates a sequence pair in place to the maximum length."""

    # This is a simple heuristic which will always truncate the longer sequence
    # one token at a time. This makes more sense than truncating an equal percent
    # of tokens from each, since if one sequence is very short then each token
    # that's truncated likely contains more information than a longer sequence.
    while True:
        total_length = len(tokens_a) + len(tokens_b)
        if total_length <= max_length:
            break
        if len(tokens_a) > len(tokens_b):
            tokens_a.pop()
        else:
            tokens_b.pop()

def warmup_linear(x, warmup=0.002):
    if x < warmup:
        return x/warmup
    return 1.0 - x

def main():
    parser = argparse.ArgumentParser()

    ## Required parameters
    parser.add_argument("--data_dir",
                        default=None,
                        type=str,
                        required=True,
                        help="The input data dir. Should contain the .tsv files (or other data files) for the task.")
    parser.add_argument("--bert_model", default=None, type=str, required=True,
                        help="Bert pre-trained model selected in the list: bert-base-uncased, "
                        "bert-large-uncased, bert-base-cased, bert-large-cased, bert-base-multilingual-uncased, "
                        "bert-base-multilingual-cased, bert-base-chinese.")
    parser.add_argument("--vocab_file", default=None, type=str, required=True,
                        help="Vocabulary file.")
    parser.add_argument("--task_name",
                        default=None,
                        type=str,
                        required=True,
                        help="The name of the task to train.")
    parser.add_argument("--output_dir",
                        default=None,
                        type=str,
                        required=True,
                        help="The output directory where the model predictions and checkpoints will be written.")

    ## Other parameters
    parser.add_argument("--max_seq_length",
                        default=128,
                        type=int,
                        help="The maximum total input sequence length after WordPiece tokenization. \n"
                             "Sequences longer than this will be truncated, and sequences shorter \n"
                             "than this will be padded.")
    parser.add_argument("--do_train",
                        action='store_true',
                        help="Whether to run training.")
    parser.add_argument("--do_eval",
                        action='store_true',
                        help="Whether to run eval on the dev set.")
    parser.add_argument("--do_lower_case",
                        action='store_true',
                        help="Set this flag if you are using an uncased model.")
    parser.add_argument("--train_batch_size",
                        default=32,
                        type=int,
                        help="Total batch size for training.")
    parser.add_argument("--eval_batch_size",
                        default=8,
                        type=int,
                        help="Total batch size for eval.")
    parser.add_argument("--learning_rate",
                        default=5e-5,
                        type=float,
                        help="The initial learning rate for Adam.")
    parser.add_argument("--num_train_epochs",
                        default=3.0,
                        type=float,
                        help="Total number of training epochs to perform.")
    parser.add_argument("--warmup_proportion",
                        default=0.1,
                        type=float,
                        help="Proportion of training to perform linear learning rate warmup for. "
                             "E.g., 0.1 = 10%% of training.")
    parser.add_argument("--no_cuda",
                        action='store_true',
                        help="Whether not to use CUDA when available")
    parser.add_argument("--local_rank",
                        type=int,
                        default=-1,
                        help="local_rank for distributed training on gpus")
    parser.add_argument('--seed',
                        type=int,
                        default=42,
                        help="random seed for initialization")
    parser.add_argument('--gradient_accumulation_steps',
                        type=int,
                        default=1,
                        help="Number of updates steps to accumulate before performing a backward/update pass.")
    parser.add_argument('--fp16',
                        action='store_true',
                        help="Whether to use 16-bit float precision instead of 32-bit")
    parser.add_argument('--loss_scale',
                        type=float, default=0,
                        help="Loss scaling to improve fp16 numeric stability. Only used when fp16 set to True.\n"
                             "0 (default value): dynamic loss scaling.\n"
                             "Positive power of 2: static loss scaling value.\n")

    #args = parser.parse_args()
    args, _ = parser.parse_known_args()

    processors = {
        "cola": ColaProcessor,
        "mnli": MnliProcessor,
        "mrpc": MrpcProcessor,
        "textqna": TextQnA,
    }

    num_labels_task = {
        "cola": 2,
        "mnli": 3,
        "mrpc": 2,
        "textqna": 2,
    }

    if args.local_rank == -1 or args.no_cuda:
        device = torch.device("cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu")
        n_gpu = torch.cuda.device_count()
    else:
        torch.cuda.set_device(args.local_rank)
        device = torch.device("cuda", args.local_rank)
        n_gpu = 1
        # Initializes the distributed backend which will take care of sychronizing nodes/GPUs
        torch.distributed.init_process_group(backend='nccl')
    logger.info("device: {} n_gpu: {}, distributed training: {}, 16-bits training: {}".format(
        device, n_gpu, bool(args.local_rank != -1), args.fp16))

    if args.gradient_accumulation_steps < 1:
        raise ValueError("Invalid gradient_accumulation_steps parameter: {}, should be >= 1".format(
                            args.gradient_accumulation_steps))

    args.train_batch_size = int(args.train_batch_size / args.gradient_accumulation_steps)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if n_gpu > 0:
        torch.cuda.manual_seed_all(args.seed)

    if not args.do_train and not args.do_eval:
        raise ValueError("At least one of `do_train` or `do_eval` must be True.")

    if os.path.exists(args.output_dir) and os.listdir(args.output_dir) and args.do_train:
        raise ValueError("Output directory ({}) already exists and is not empty.".format(args.output_dir))
    os.makedirs(args.output_dir, exist_ok=True)

    task_name = args.task_name.lower()

    if task_name not in processors:
        raise ValueError("Task not found: %s" % (task_name))

    processor = processors[task_name]()
    num_labels = num_labels_task[task_name]
    label_list = processor.get_labels()

    tokenizer = BertTokenizer.from_pretrained(args.vocab_file, do_lower_case=args.do_lower_case)

    train_examples = None
    num_train_steps = None
    if args.do_train:
        train_examples = processor.get_train_examples(args.data_dir)
        num_train_steps = int(
            len(train_examples) / args.train_batch_size / args.gradient_accumulation_steps * args.num_train_epochs)

    # Prepare model
    #model = BertForFullSequenceRelevance.from_pretrained(args.bert_model, device="cpu")
    model = BertForFullSequenceRelevance.from_pretrained(args.bert_model, device="cuda")
    
    if args.fp16:
        model.half()
    model.to(device)
    if args.local_rank != -1:
        try:
            from apex.parallel import DistributedDataParallel as DDP
        except ImportError:
            raise ImportError("Please install apex from https://www.github.com/nvidia/apex to use distributed and fp16 training.")

        model = DDP(model)
    elif n_gpu > 1:
        model = torch.nn.DataParallel(model)

    # Prepare optimizer
    param_optimizer = list(model.named_parameters())
    no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
    optimizer_grouped_parameters = [
        {'params': [p for n, p in param_optimizer if not any(nd in n for nd in no_decay)], 'weight_decay': 0.01},
        {'params': [p for n, p in param_optimizer if any(nd in n for nd in no_decay)], 'weight_decay': 0.0}
        ]
    t_total = num_train_steps
    if args.local_rank != -1:
        t_total = t_total // torch.distributed.get_world_size()
    if args.fp16:
        try:
            from apex.optimizers import FP16_Optimizer
            from apex.optimizers import FusedAdam
        except ImportError:
            raise ImportError("Please install apex from https://www.github.com/nvidia/apex to use distributed and fp16 training.")

        optimizer = FusedAdam(optimizer_grouped_parameters,
                              lr=args.learning_rate,
                              bias_correction=False,
                              max_grad_norm=1.0)
        if args.loss_scale == 0:
            optimizer = FP16_Optimizer(optimizer, dynamic_loss_scale=True)
        else:
            optimizer = FP16_Optimizer(optimizer, static_loss_scale=args.loss_scale)

    else:
        optimizer = BertAdam(optimizer_grouped_parameters,
                             lr=args.learning_rate,
                             warmup=args.warmup_proportion,
                             t_total=t_total)

    global_step = 0
    nb_tr_steps = 0
    tr_loss = 0
    train_epoch = 0

    if args.do_train:
        train_features = convert_examples_to_relevance_features(train_examples, label_list, args.max_seq_length, tokenizer)
        #train_features = convert_examples_to_features(
        #    train_examples, label_list, args.max_seq_length, tokenizer)
        
        logger.info("***** Running training *****")
        logger.info("  Num examples = %d", len(train_examples))
        logger.info("  Batch size = %d", args.train_batch_size)
        logger.info("  Num steps = %d", num_train_steps)
        
        all_query_ids = torch.tensor([f.query_ids for f in train_features], dtype=torch.long)
        all_psg_ids = torch.tensor([f.psg_ids for f in train_features], dtype=torch.long)
        all_query_mask = torch.tensor([f.query_mask for f in train_features], dtype=torch.long)
        all_psg_mask = torch.tensor([f.psg_mask for f in train_features], dtype=torch.long)
        all_query_segment_ids = torch.tensor([f.query_segment_ids for f in train_features], dtype=torch.long)
        all_psg_segment_ids = torch.tensor([f.psg_segment_ids for f in train_features], dtype=torch.long)
        all_labels_id = torch.tensor([f.label_id for f in train_features], dtype=torch.long)
        train_data = TensorDataset(all_query_ids, all_psg_ids, all_query_mask, all_psg_mask, all_query_segment_ids, all_psg_segment_ids, all_labels_id)

        if args.local_rank == -1:
            train_sampler = RandomSampler(train_data)
        else:
            train_sampler = DistributedSampler(train_data)
        train_dataloader = DataLoader(train_data, sampler=train_sampler, batch_size=args.train_batch_size)

        model.train()
        for _ in trange(int(args.num_train_epochs), desc="Epoch"):
            tr_loss = 0
            nb_tr_examples, nb_tr_steps = 0, 0
            for step, batch in enumerate(tqdm(train_dataloader, desc="Iteration")):
                batch = tuple(t.to(device) for t in batch)
                query_ids, psg_ids, query_mask, psg_mask, query_segment_ids, psg_segment_ids, labels_id = batch 
                loss = model(query_ids, psg_ids, query_mask, psg_mask, query_segment_ids, psg_segment_ids, labels_id)
               
                if n_gpu > 1:
                    loss = loss.mean() # mean() to average on multi-gpu.
                if args.gradient_accumulation_steps > 1:
                    loss = loss / args.gradient_accumulation_steps

                if args.fp16:
                    optimizer.backward(loss)
                else:
                    loss.backward()

                tr_loss += loss.item()
                nb_tr_examples += query_ids.size(0)
                nb_tr_steps += 1
                if (step + 1) % args.gradient_accumulation_steps == 0:
                    # modify learning rate with special warm up BERT uses
                    lr_this_step = args.learning_rate * warmup_linear(global_step/t_total, args.warmup_proportion)
                    for param_group in optimizer.param_groups:
                        param_group['lr'] = lr_this_step
                    optimizer.step()
                    optimizer.zero_grad()
                    global_step += 1

            # Save a trained model
            model_to_save = model.module if hasattr(model, 'module') else model # Only save the model it-self
            out_model_filename = "pytorch_model_" + str(train_epoch) + ".bin"
            output_model_file = os.path.join(args.output_dir, out_model_filename)
            torch.save(model_to_save.state_dict(), output_model_file)
            train_epoch += 1

    if args.do_eval and (args.local_rank == -1 or torch.distributed.get_rank() == 0):
        
        eval_examples = processor.get_dev_examples(args.data_dir)
        eval_features = convert_examples_to_relevance_features(eval_examples, label_list, args.max_seq_length, tokenizer)

        logger.info("***** Running evaluation *****")
        logger.info("  Dev Num examples = %d", len(eval_examples))
        logger.info("  Dev Batch size = %d", args.eval_batch_size)
        
        eval_query_ids = torch.tensor([f.query_ids for f in eval_features], dtype=torch.long)
        eval_psg_ids = torch.tensor([f.psg_ids for f in eval_features], dtype=torch.long)
        eval_query_mask = torch.tensor([f.query_mask for f in eval_features], dtype=torch.long)
        eval_psg_mask = torch.tensor([f.psg_mask for f in eval_features], dtype=torch.long)
        eval_query_segment_ids = torch.tensor([f.query_segment_ids for f in eval_features], dtype=torch.long)
        eval_psg_segment_ids = torch.tensor([f.psg_segment_ids for f in eval_features], dtype=torch.long)
        eval_labels_id = torch.tensor([f.label_id for f in eval_features], dtype=torch.long)
        eval_data = TensorDataset(eval_query_ids, eval_psg_ids, eval_query_mask, eval_psg_mask, eval_query_segment_ids, eval_psg_segment_ids, eval_labels_id)
        # Run prediction for full data
        eval_sampler = SequentialSampler(eval_data)
        eval_dataloader = DataLoader(eval_data, sampler=eval_sampler, batch_size=args.eval_batch_size)

        # Processing Testing Data
        test_examples = processor.get_test_examples(args.data_dir)
        test_features = convert_examples_to_relevance_features(test_examples, label_list, args.max_seq_length, tokenizer)

        logger.info("  Test Num examples = %d", len(test_examples))
        logger.info("  Test Batch size = %d", args.eval_batch_size)

        test_query_ids = torch.tensor([f.query_ids for f in test_features], dtype=torch.long)
        test_psg_ids = torch.tensor([f.psg_ids for f in test_features], dtype=torch.long)
        test_query_mask = torch.tensor([f.query_mask for f in test_features], dtype=torch.long)
        test_psg_mask = torch.tensor([f.psg_mask for f in test_features], dtype=torch.long)
        test_query_segment_ids = torch.tensor([f.query_segment_ids for f in test_features], dtype=torch.long)
        test_psg_segment_ids = torch.tensor([f.psg_segment_ids for f in test_features], dtype=torch.long)
        test_labels_id = torch.tensor([f.label_id for f in test_features], dtype=torch.long)
        test_data = TensorDataset(test_query_ids, test_psg_ids, test_query_mask, test_psg_mask, test_query_segment_ids, test_psg_segment_ids, test_labels_id)
    
        # Run prediction for full data
        test_sampler = SequentialSampler(test_data)
        test_dataloader = DataLoader(test_data, sampler=test_sampler, batch_size=args.eval_batch_size)

        for cur_epoch in range(int(args.num_train_epochs)):
            print("cur_epoch: ", cur_epoch)
            # Load a trained model that you have fine-tuned
            saved_model_filename =  "pytorch_model_" + str(cur_epoch) + ".bin"
            saved_model_file =  os.path.join(args.output_dir, saved_model_filename)
            model_state_dict = torch.load(saved_model_file)
            #model = BertForFullSequenceRelevance.from_pretrained(args.bert_model, state_dict=model_state_dict, device="cpu")
            model = BertForFullSequenceRelevance.from_pretrained(args.bert_model, state_dict=model_state_dict, device="cuda")
            model.to(device)

            model.eval()
            eval_score_list = np.array([])
            eval_label_list = np.array([])
            nb_eval_steps, nb_eval_examples = 0, 0
 
            for query_ids, psg_ids, query_mask, psg_mask, query_segment_ids, psg_segment_ids, labels_id in tqdm(eval_dataloader, desc="Evaluating"):
                
                query_ids = query_ids.to(device)
                psg_ids = psg_ids.to(device)
                query_mask = query_mask.to(device)
                psg_mask = psg_mask.to(device)
                query_segment_ids = query_segment_ids.to(device)
                psg_segment_ids = psg_segment_ids.to(device)
                labels_id = labels_id.to(device)
                
                with torch.no_grad():
                    logits = model(query_ids, psg_ids, query_mask, psg_mask, query_segment_ids, psg_segment_ids)

                logits = logits.detach().cpu().numpy()
                labels_id = labels_id.to('cpu').numpy()
                eval_score_list = np.append(eval_score_list, logits[:, 0])
                eval_label_list = np.append(eval_label_list, labels_id)

                nb_eval_examples += query_ids.size(0)
                nb_eval_steps += 1
                
            eval_auc = metrics.calAUC(eval_score_list, eval_label_list)

            test_score_list = np.array([])
            test_label_list = np.array([])
            nb_test_steps, nb_test_examples = 0, 0

            for query_ids, psg_ids, query_mask, psg_mask, query_segment_ids, psg_segment_ids, labels_id in tqdm(test_dataloader, desc="Evaluating"):

                query_ids = query_ids.to(device)
                psg_ids = psg_ids.to(device)
                query_mask = query_mask.to(device)
                psg_mask = psg_mask.to(device)
                query_segment_ids = query_segment_ids.to(device)
                psg_segment_ids = psg_segment_ids.to(device)
                labels_id = labels_id.to(device)

                with torch.no_grad():
                    logits = model(query_ids, psg_ids, query_mask, psg_mask, query_segment_ids, psg_segment_ids)

                logits = logits.detach().cpu().numpy()
                labels_id = labels_id.to('cpu').numpy()
                test_score_list = np.append(test_score_list, logits[:, 0])
                test_label_list = np.append(test_label_list, labels_id)

                nb_test_examples += query_ids.size(0)
                nb_test_steps += 1

            test_auc = metrics.calAUC(test_score_list, test_label_list)

            result = {'cur_epoch': cur_epoch,
                    'eval_AUC': eval_auc,
                    'eval_counts': nb_eval_examples,
                    'test_AUC': test_auc,
                    'test_counts': nb_test_examples
                    }

            output_eval_file = os.path.join(args.output_dir, "eval_results.txt")
            with open(output_eval_file, "a+") as writer:
                logger.info("***** Eval results *****")
                for key in sorted(result.keys()):
                    logger.info("  %s = %s", key, str(result[key]))
                    writer.write("%s = %s\n" % (key, str(result[key])))
                writer.write("\n")

if __name__ == "__main__":
    main()