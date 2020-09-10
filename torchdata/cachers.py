r"""**This module contains interface needed for** `cachers` **(used in** `cache` **method of** `td.Dataset` **) .**

To cache on disk all samples using Python's `pickle <https://docs.python.org/3/library/pickle.html>`__ in folder `cache`
(assuming you have already created `td.Dataset` instance named `dataset`)::

    import torchdata as td

    ...
    dataset.cache(td.cachers.Pickle("./cache"))

Users are encouraged to write their custom `cachers` if the ones provided below
are too slow or not good enough for their purposes (see `Cacher` abstract interface below).

"""

import abc
import pathlib
import pickle
import shutil
import typing

import torch

from ._base import Base


class Cacher(Base):
    r"""**Interface to fulfil to make object compatible with** `torchdata.Dataset.cache` **method.**

    If you want to implement your own `caching` functionality, inherit from
    this class and implement methods described below.
    """

    @abc.abstractmethod
    def __contains__(self, index: int) -> bool:
        r"""**Return true if sample under** `index` **is cached.**

        If `False` returned, cacher's `__setitem__` will be called, hence if you are not
        going to cache sample under this `index`, you should describe this operation
        at that method.
        This is simply a boolean indicator whether sample is cached.

        If `True` cacher's `__getitem__` will be called and it's users responsibility
        to return correct value in such case.

        Parameters
        ----------
        index : int
                Index of sample
        """

    # Save if doesn't contain
    @abc.abstractmethod
    def __setitem__(self, index: int, data: typing.Any) -> None:
        r"""**Saves sample under index in cache or do nothing.**

        This function should save sample under `index` to be later
        retrieved by `__getitem__`.
        If you don't want to save specific `index`, you can implement this functionality
        in `cacher` or create separate `modifier` solely for this purpose
        (second approach is highly recommended).

        Parameters
        ----------
        index : int
                Index of sample
        data : Any
                Data generated by dataset.
        """

    # Save if doesn't contain
    @abc.abstractmethod
    def __getitem__(self, index) -> typing.Any:
        r"""**Retrieve sample from cache.**

        **This function MUST return valid data sample and it's users responsibility
        if custom cacher is implemented**.

        Return from this function datasample which lies under it's respective
        `index`.

        Parameters
        ----------
        index : int
                Index of sample
        """


class Pickle(Cacher):
    r"""**Save and load data from disk using** `pickle` **module.**

    Data will be saved as `.pkl` in specified path. If path does not exist,
    it will be created.

    **This object can be used as a** `context manager` **and it will delete** `path` **at the end of block**::

        with td.cachers.Pickle(pathlib.Path("./disk")) as pickler:
            dataset = dataset.map(lambda x: x+1).cache(pickler)
            ... # Do something with dataset
        ... # Folder removed

    You can also issue `clean()` method manually for the same effect
    (though it's discouraged as you might crash `__setitem__` method).


    .. note::

        This `cacher` can act between consecutive runs, just don't use `clean()` method
        or don't delete the folder manually. If so, **please ensure correct sampling**
        (same seed and sampling order) for reproducible behaviour between runs.


    Attributes
    ----------
    path: pathlib.Path
            Path to the folder where samples will be saved and loaded from.
    extension: str
            Extension to use for saved pickle files. Default: `.pkl`

    """

    def __init__(self, path: pathlib.Path, extension: str = ".pkl"):
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
        self.extension = extension

    def __contains__(self, index: int) -> bool:
        """**Check whether file exists on disk.**

        If file is available it is considered cached, hence you can cache data
        between multiple runs (if you ensure repeatable sampling).

        """
        return pathlib.Path(
            (self.path / str(index)).with_suffix(self.extension)
        ).is_file()

    def __setitem__(self, index: int, data: int):
        """**Save** `data` **in specified folder.**

        Name of the item will be equal to `{self.path}/{index}{extension}`.

        """
        with open((self.path / str(index)).with_suffix(self.extension), "wb") as file:
            pickle.dump(data, file)

    def __getitem__(self, index: int):
        """**Retrieve** `data` **specified by** `index`.

        Name of the item will be equal to `{self.path}/{index}{extension}`.

        """
        with open((self.path / str(index)).with_suffix(self.extension), "rb") as file:
            return pickle.load(file)

    def clean(self) -> None:
        """**Remove recursively folder** `self.path`.

        Behaves just like `shutil.rmtree`, but won't act if directory does not exist.
        """

        if self.path.is_dir():
            shutil.rmtree(self.path)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.clean()


class Memory(Cacher):
    r"""**Save and load data in Python dictionary**.

    This `cacher` is used by default inside `torchdata.Dataset`.

    """

    def __init__(self):
        self.cache = {}

    def __contains__(self, index: int) -> bool:
        """True if index in dictionary."""
        return index in self.cache

    def __setitem__(self, index: int, data: int):
        """Adds data to dictionary."""
        self.cache[index] = data

    def __getitem__(self, index: int):
        """Retrieve data from dictionary."""
        return self.cache[index]


class Tensor(Cacher):
    r"""**Save and load data from disk using PyTorch's ** `save` **function.**

    Tensors will be saved as `.pt` in specified path. If path does not exist,
    it will be created.

    **This object can be used as a** `context manager` **and it will delete** `path` **at the end of block**::

        with td.cachers.Tensor(pathlib.Path("./disk")) as cacher:
            dataset = dataset.map(lambda x: x+1).cache(cacher)
            ... # Do something with dataset
        ... # Folder removed

    You can also issue `clean()` method manually for the same effect
    (though it's discouraged as you might crash `__setitem__` method).


    .. note::

        This `cacher` can act between consecutive runs, just don't use `clean()` method
        or don't delete the folder manually. If so, **please ensure correct sampling**
        (same seed and sampling order) for reproducible behaviour between runs.

    Attributes
    ----------
    path: pathlib.Path
        Path to the folder where samples will be saved and loaded from.
    extension: str
        Extension to use for saved pickle files. Default: `.pt`
    map_location: a function, :class:`torch.device`, string, dict, optional
        Specify how to remap storage locations. See `torch.load`. Default: `None`
    pickle_module: module, optional
        Module used for unpickling metadata and objects (has to
        match the :attr:`pickle_module` used to serialize file).
        Default: `pickle`
    pickle_protocol: int, optional
        Can be specified to override the default protocol. See `torch.save`.
        Default: `2` (`pickle` default)
    **pickle_load_args
        optional keyword arguments passed over to :func:`pickle_module.load`
        and :func:`pickle_module.Unpickler`, e.g., :attr:`errors=...`.
        See `torch.load`

    """

    def __init__(
        self,
        path: pathlib.Path,
        extension: str = ".pt",
        map_location=None,
        pickle_module=pickle,
        pickle_protocol=2,
        **pickle_load_args
    ):
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
        self.extension = extension
        self.map_location = map_location
        self.pickle_module = pickle_module
        self.pickle_protocol = pickle_protocol
        self.pickle_load_args = pickle_load_args

    def __contains__(self, index: int) -> bool:
        """**Check whether file exists on disk.**

        If file is available it is considered cached, hence you can cache data
        between multiple runs (if you ensure repeatable sampling).

        """
        return pathlib.Path(
            (self.path / str(index)).with_suffix(self.extension)
        ).is_file()

    def __setitem__(self, index: int, data: int):
        """**Save** `data` **in specified folder.**

        Name of the item will be equal to `{self.path}/{index}{extension}`.

        """
        torch.save(
            data,
            (self.path / str(index)).with_suffix(self.extension),
            pickle_module=self.pickle_module,
            pickle_protocol=self.pickle_protocol,
        )

    def __getitem__(self, index: int):
        """**Retrieve** `data` **specified by** `index`.

        Name of the item will be equal to `{self.path}/{index}{extension}`.

        """
        torch.load(
            (self.path / str(index)).with_suffix(self.extension),
            map_location=self.map_location,
            pickle_module=self.pickle_module,
            **self.pickle_load_args
        )

    def clean(self) -> None:
        """**Remove recursively folder** `self.path`.

        Behaves just like `shutil.rmtree`, but won't act if directory does not exist.
        """

        if self.path.is_dir():
            shutil.rmtree(self.path)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.clean()
