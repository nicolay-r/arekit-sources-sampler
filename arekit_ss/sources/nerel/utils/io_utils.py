from os import path

from arekit.common.experiment.data_type import DataType

from arekit_ss.core.source.zip_utils import ZipArchiveUtils
from arekit_ss.sources.nerel.utils.folding.fixed import create_fixed_folding
from arekit_ss.sources.nerel.utils.utils import iter_filename_and_splittype


class NerelIOUtils(ZipArchiveUtils):

    splits = {
        DataType.Train: "train",
        DataType.Dev: "dev",
        DataType.Test: "test"
    }

    @staticmethod
    def get_archive_filepath(version):
        return path.join(NerelIOUtils.get_data_root(), "nerel-{}.zip".format(version))

    @staticmethod
    def get_annotation_innerpath(folding_data_type, filename):
        assert(isinstance(filename, str))
        return path.join(NerelIOUtils.splits[folding_data_type], "{}.ann".format(filename))

    @staticmethod
    def get_news_innerpath(folding_data_type, filename):
        assert(isinstance(filename, str))
        return path.join(NerelIOUtils.splits[folding_data_type], "{}.txt".format(filename))

    @staticmethod
    def map_doc_to_fold_type(version):

        it = iter_filename_and_splittype(
            filenames_it=NerelIOUtils.iter_filenames_from_zip(version),
            splits=NerelIOUtils.splits.items())

        d2f = {}
        for filename, split_type in it:
            d2f[filename] = split_type

        return d2f

    @staticmethod
    def read_dataset_split(version, docs_limit=None):

        it = iter_filename_and_splittype(
            filenames_it=NerelIOUtils.iter_filenames_from_zip(version),
            splits=NerelIOUtils.splits.items())

        f2d = {}
        for filename, split_type in it:
            if split_type not in f2d:
                f2d[split_type] = []
            f2d[split_type].append(filename)

        filenames_by_ids, data_folding = create_fixed_folding(train_filenames=f2d[DataType.Train],
                                                              test_filenames=f2d[DataType.Test],
                                                              dev_filenames=f2d[DataType.Dev],
                                                              limit=docs_limit)

        return filenames_by_ids, data_folding
