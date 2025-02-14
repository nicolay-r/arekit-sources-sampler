import unittest
from collections import OrderedDict
from os.path import dirname, join

from arekit.common.experiment.data_type import DataType
from arekit.common.frames.variants.collection import FrameVariantsCollection
from arekit.common.labels.base import Label, NoLabel
from arekit.common.labels.scaler.sentiment import SentimentLabelScaler
from arekit.common.labels.str_fmt import StringLabelsFormatter
from arekit.common.pipeline.base import BasePipelineLauncher
from arekit.common.pipeline.context import PipelineContext
from arekit.contrib.networks.input.ctx_serialization import NetworkSerializationContext
from arekit.contrib.utils.data.readers.csv_pd import PandasCsvReader
from arekit.contrib.utils.data.storages.pandas_based import PandasBasedRowsStorage
from arekit.contrib.utils.data.writers.csv_pd import PandasCsvWriter
from arekit.contrib.utils.entities.formatters.str_display import StringEntitiesDisplayValueFormatter
from arekit.contrib.utils.io_utils.embedding import NpEmbeddingIO
from arekit.contrib.utils.pipelines.items.sampling.networks import NetworksInputSerializerPipelineItem
from arekit.contrib.utils.pipelines.items.text.frames_lemmatized import LemmasBasedFrameVariantsParser
from arekit.contrib.utils.pipelines.text_opinion.extraction import text_opinion_extraction_pipeline
from arekit.contrib.utils.pipelines.text_opinion.filters.distance_based import DistanceLimitedTextOpinionFilter

from arekit_ss.core.samples_io import CustomSamplesIO
from arekit_ss.core.source.brat.entities.parser import BratTextEntitiesParser
from arekit_ss.core.utils.nn.rows import create_rows_provider
from arekit_ss.pipelines.annot.predefined import PredefinedTextOpinionAnnotator
from arekit_ss.pipelines.text.tokenizer import DefaultTextTokenizer
from arekit_ss.pos.ru_mystem import POSMystemWrapper
from arekit_ss.sources.rusentiframes.collection import RuSentiFramesCollection
from arekit_ss.sources.rusentiframes.connotations.rusentiframes_sentiment import RuSentiFramesConnotationProvider
from arekit_ss.sources.rusentiframes.labels_fmt import RuSentiFramesLabelsFormatter, RuSentiFramesEffectLabelsFormatter
from arekit_ss.sources.rusentiframes.types import RuSentiFramesVersions
from arekit_ss.stemmers.ru_mystem import MystemWrapper
from test_tutorial_pipeline_text_opinion_annotation import FooDocumentProvider


class Positive(Label):
    pass


class Negative(Label):
    pass


class CustomSentimentLabelScaler(SentimentLabelScaler):
    def __init__(self):
        int_to_label = OrderedDict([(NoLabel(), 0), (Positive(), 1), (Negative(), -1)])
        uint_to_label = OrderedDict([(NoLabel(), 0), (Positive(), 1), (Negative(), 2)])
        super(SentimentLabelScaler, self).__init__(int_dict=int_to_label, uint_dict=uint_to_label)

    def invert_label(self, label):
        int_label = self.label_to_int(label)
        return self.int_to_label(-int_label)


class CustomLabelsFormatter(StringLabelsFormatter):
    def __init__(self, pos_label_type, neg_label_type):
        stol = {"POSITIVE_TO": neg_label_type, "NEGATIVE_TO": pos_label_type}
        super(CustomLabelsFormatter, self).__init__(stol=stol)


class TestSamplingNetwork(unittest.TestCase):

    __output_dir = join(dirname(__file__), "out")

    def test(self):

        stemmer = MystemWrapper()

        frames_collection = RuSentiFramesCollection.read(
            version=RuSentiFramesVersions.V20,
            labels_fmt=RuSentiFramesLabelsFormatter(pos_label_type=Positive, neg_label_type=Negative),
            effect_labels_fmt=RuSentiFramesEffectLabelsFormatter(pos_label_type=Positive, neg_label_type=Negative))

        frame_variant_collection = FrameVariantsCollection()
        frame_variant_collection.fill_from_iterable(
            variants_with_id=frames_collection.iter_frame_id_and_variants(),
            overwrite_existed_variant=True,
            raise_error_on_existed_variant=False)

        ctx = NetworkSerializationContext(
            labels_scaler=CustomSentimentLabelScaler(),
            pos_tagger=POSMystemWrapper(mystem=stemmer.MystemInstance),
            frame_roles_label_scaler=CustomSentimentLabelScaler(),
            frames_connotation_provider=RuSentiFramesConnotationProvider(frames_collection))

        writer = PandasCsvWriter(write_header=True)

        rows_provider = create_rows_provider(
            str_entity_fmt=StringEntitiesDisplayValueFormatter(),
            ctx=ctx)

        pipeline_item = NetworksInputSerializerPipelineItem(
            samples_io=CustomSamplesIO(self.__output_dir, writer),
            emb_io=NpEmbeddingIO(target_dir=self.__output_dir),
            rows_provider=rows_provider,
            save_labels_func=lambda data_type: data_type != DataType.Test,
            storage=PandasBasedRowsStorage(),
            src_key=None)

        #####
        # Declaring pipeline related context parameters.
        #####
        doc_provider = FooDocumentProvider()
        pipeline_items = [
            BratTextEntitiesParser(),
            DefaultTextTokenizer(keep_tokens=True),
            LemmasBasedFrameVariantsParser(frame_variants=frame_variant_collection, stemmer=stemmer)
        ]
        train_pipeline = text_opinion_extraction_pipeline(
            annotators=[
                PredefinedTextOpinionAnnotator(
                    doc_provider,
                    label_formatter=CustomLabelsFormatter(pos_label_type=Positive, neg_label_type=Negative))
            ],
            text_opinion_filters=[
                DistanceLimitedTextOpinionFilter(terms_per_context=50)
            ],
            get_doc_by_id_func=doc_provider.by_id,
            entity_index_func=lambda brat_entity: brat_entity.ID,
            pipeline_items=pipeline_items)
        #####

        BasePipelineLauncher.run(
            pipeline=[pipeline_item],
            pipeline_ctx=PipelineContext(d={
             "data_type_pipelines": {DataType.Train: train_pipeline},
             "data_folding": {DataType.Train: [0, 1]}
            }))

        reader = PandasCsvReader()
        source = join(self.__output_dir, "sample-train" + writer.extension())
        storage = reader.read(source)
        self.assertEqual(20, len(storage), "Amount of rows is non equal!")


if __name__ == '__main__':
    unittest.main()
