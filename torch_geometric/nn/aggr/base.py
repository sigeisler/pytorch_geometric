from typing import Optional, Tuple

import torch
from torch import Tensor

from torch_geometric.experimental import disable_dynamic_shapes
from torch_geometric.utils import scatter, segment, to_dense_batch


class Aggregation(torch.nn.Module):
    r"""An abstract base class for implementing custom aggregations.

    Aggregation can be either performed via an :obj:`index` vector, which
    defines the mapping from input elements to their location in the output:

    |

    .. image:: https://raw.githubusercontent.com/rusty1s/pytorch_scatter/
            master/docs/source/_figures/add.svg?sanitize=true
        :align: center
        :width: 400px

    |

    Notably, :obj:`index` does not have to be sorted (for most aggregation
    operators):

    .. code-block::

       # Feature matrix holding 10 elements with 64 features each:
       x = torch.randn(10, 64)

       # Assign each element to one of three sets:
       index = torch.tensor([0, 0, 1, 0, 2, 0, 2, 1, 0, 2])

       output = aggr(x, index)  #  Output shape: [3, 64]

    Alternatively, aggregation can be achieved via a "compressed" index vector
    called :obj:`ptr`. Here, elements within the same set need to be grouped
    together in the input, and :obj:`ptr` defines their boundaries:

    .. code-block::

       # Feature matrix holding 10 elements with 64 features each:
       x = torch.randn(10, 64)

       # Define the boundary indices for three sets:
       ptr = torch.tensor([0, 4, 7, 10])

       output = aggr(x, ptr=ptr)  #  Output shape: [4, 64]

    Note that at least one of :obj:`index` or :obj:`ptr` must be defined.

    Shapes:
        - **input:**
          node features :math:`(*, |\mathcal{V}|, F_{in})` or edge features
          :math:`(*, |\mathcal{E}|, F_{in})`,
          index vector :math:`(|\mathcal{V}|)` or :math:`(|\mathcal{E}|)`,
        - **output:** graph features :math:`(*, |\mathcal{G}|, F_{out})` or
          node features :math:`(*, |\mathcal{V}|, F_{out})`
    """
    def forward(
        self,
        x: Tensor,
        index: Optional[Tensor] = None,
        ptr: Optional[Tensor] = None,
        dim_size: Optional[int] = None,
        dim: int = -2,
        max_num_elements: Optional[int] = None,
    ) -> Tensor:
        r"""
        Args:
            x (torch.Tensor): The source tensor.
            index (torch.Tensor, optional): The indices of elements for
                applying the aggregation.
                One of :obj:`index` or :obj:`ptr` must be defined.
                (default: :obj:`None`)
            ptr (torch.Tensor, optional): If given, computes the aggregation
                based on sorted inputs in CSR representation.
                One of :obj:`index` or :obj:`ptr` must be defined.
                (default: :obj:`None`)
            dim_size (int, optional): The size of the output tensor at
                dimension :obj:`dim` after aggregation. (default: :obj:`None`)
            dim (int, optional): The dimension in which to aggregate.
                (default: :obj:`-2`)
            max_num_elements: (int, optional): The maximum number of elements
                within a single aggregation group. (default: :obj:`None`)
        """
        pass

    def reset_parameters(self):
        r"""Resets all learnable parameters of the module."""
        pass

    @disable_dynamic_shapes(required_args=['dim_size'])
    def __call__(
        self,
        x: Tensor,
        index: Optional[Tensor] = None,
        ptr: Optional[Tensor] = None,
        dim_size: Optional[int] = None,
        dim: int = -2,
        **kwargs,
    ) -> Tensor:

        if dim >= x.dim() or dim < -x.dim():
            raise ValueError(f"Encountered invalid dimension '{dim}' of "
                             f"source tensor with {x.dim()} dimensions")

        if index is None and ptr is None:
            index = x.new_zeros(x.size(dim), dtype=torch.long)

        if ptr is not None:
            if dim_size is None:
                dim_size = ptr.numel() - 1
            elif dim_size != ptr.numel() - 1:
                raise ValueError(f"Encountered invalid 'dim_size' (got "
                                 f"'{dim_size}' but expected "
                                 f"'{ptr.numel() - 1}')")

        if index is not None and dim_size is None:
            dim_size = int(index.max()) + 1 if index.numel() > 0 else 0

        try:
            return super().__call__(x, index=index, ptr=ptr, dim_size=dim_size,
                                    dim=dim, **kwargs)
        except (IndexError, RuntimeError) as e:
            if index is not None:
                if index.numel() > 0 and dim_size <= int(index.max()):
                    raise ValueError(f"Encountered invalid 'dim_size' (got "
                                     f"'{dim_size}' but expected "
                                     f">= '{int(index.max()) + 1}')")
            raise e

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}()'

    # Assertions ##############################################################

    def assert_index_present(self, index: Optional[Tensor]):
        # TODO Currently, not all aggregators support `ptr`. This assert helps
        # to ensure that we require `index` to be passed to the computation:
        if index is None:
            raise NotImplementedError(
                "Aggregation requires 'index' to be specified")

    def assert_sorted_index(self, index: Optional[Tensor]):
        if index is not None and not torch.all(index[:-1] <= index[1:]):
            raise ValueError("Can not perform aggregation since the 'index' "
                             "tensor is not sorted. Specifically, if you use "
                             "this aggregation as part of 'MessagePassing`, "
                             "ensure that 'edge_index' is sorted by "
                             "destination nodes, e.g., by calling "
                             "`data.sort(sort_by_row=False)`")

    def assert_two_dimensional_input(self, x: Tensor, dim: int):
        if x.dim() != 2:
            raise ValueError(f"Aggregation requires two-dimensional inputs "
                             f"(got '{x.dim()}')")

        if dim not in [-2, 0]:
            raise ValueError(f"Aggregation needs to perform aggregation in "
                             f"first dimension (got '{dim}')")

    # Helper methods ##########################################################

    def reduce(
        self,
        x: Tensor,
        index: Optional[Tensor] = None,
        ptr: Optional[Tensor] = None,
        dim_size: Optional[int] = None,
        dim: int = -2,
        reduce: str = 'sum',
    ) -> Tensor:

        if ptr is not None:
            ptr = expand_left(ptr, dim, dims=x.dim())
            return segment(x, ptr, reduce=reduce)

        assert index is not None
        return scatter(x, index, dim, dim_size, reduce)

    def to_dense_batch(
        self,
        x: Tensor,
        index: Optional[Tensor] = None,
        ptr: Optional[Tensor] = None,
        dim_size: Optional[int] = None,
        dim: int = -2,
        fill_value: float = 0.0,
        max_num_elements: Optional[int] = None,
    ) -> Tuple[Tensor, Tensor]:

        # TODO Currently, `to_dense_batch` can only operate on `index`:
        self.assert_index_present(index)
        self.assert_sorted_index(index)
        self.assert_two_dimensional_input(x, dim)

        return to_dense_batch(
            x,
            index,
            batch_size=dim_size,
            fill_value=fill_value,
            max_num_nodes=max_num_elements,
        )


class WeightedAggregation(Aggregation):
    r"""An abstract base class for implementing custom weighted aggregations.

    In addition to :obj:`Aggregation`, :class:`WeightedAggregation` assigns a
    custom :obj:`weight` value to each element in the input tensor :obj:`x`.

    Shapes:
        - **input:**
          node features :math:`(*, |\mathcal{V}|, F_{in})` or edge features
          :math:`(*, |\mathcal{E}|, F_{in})`,
          node weights :math:`(|\mathcal{V}|)` or edge weights
          :math:`(|\mathcal{E}|)`,
          index vector :math:`(|\mathcal{V}|)` or :math:`(|\mathcal{E}|)`,
        - **output:** graph features :math:`(*, |\mathcal{G}|, F_{out})` or
          node features :math:`(*, |\mathcal{V}|, F_{out})`
    """
    def forward(
        self,
        x: Tensor,
        index: Optional[Tensor] = None,
        weight: Optional[Tensor] = None,
        ptr: Optional[Tensor] = None,
        dim_size: Optional[int] = None,
        dim: int = -2,
    ) -> Tensor:
        r"""
        Args:
            x (torch.Tensor): The source tensor.
            index (torch.Tensor, optional): The indices of elements for
                applying the aggregation.
                One of :obj:`index` or :obj:`ptr` must be defined.
                (default: :obj:`None`)
            weight (torch.Tensor, optional): The weight vector.
            ptr (torch.Tensor, optional): If given, computes the aggregation
                based on sorted inputs in CSR representation.
                One of :obj:`index` or :obj:`ptr` must be defined.
                (default: :obj:`None`)
            dim_size (int, optional): The size of the output tensor at
                dimension :obj:`dim` after aggregation. (default: :obj:`None`)
            dim (int, optional): The dimension in which to aggregate.
                (default: :obj:`-2`)
        """
        pass

    def __call__(
        self,
        x: Tensor,
        index: Optional[Tensor] = None,
        weight: Optional[Tensor] = None,
        ptr: Optional[Tensor] = None,
        dim_size: Optional[int] = None,
        dim: int = -2,
        **kwargs,
    ) -> Tensor:

        if index is None and ptr is None:
            index = x.new_zeros(x.size(dim), dtype=torch.long)

        if weight is not None and weight.dim() != 1:
            raise ValueError(f"The 'weight' vector needs to be one-"
                             f"dimensional (got {weight.dim()} dimensions)")

        if weight is not None and weight.size(0) != x.size(dim):
            raise ValueError(f"The input tensor has {x.size(dim)} elements, "
                             f"but the 'weight' vector holds {weight.size(0)} "
                             f"elements. Please make sure that the size of "
                             f"the inputs align")

        return super().__call__(x, weight=weight, index=index, ptr=ptr,
                                dim_size=dim_size, dim=dim, **kwargs)

    # Helper methods ##########################################################

    def weighted_reduce(
        self,
        x: Tensor,
        index: Optional[Tensor] = None,
        weight: Optional[Tensor] = None,
        ptr: Optional[Tensor] = None,
        dim_size: Optional[int] = None,
        dim: int = -2,
        reduce: str = 'sum',
    ) -> Tensor:

        sizes = [1] * x.dim()
        sizes[dim] = x.size(dim)

        self.assert_weight_present(weight)

        weight = weight.view(sizes)

        if ptr is not None:
            ptr = expand_left(ptr, dim, dims=x.dim())

            shape = [1] * x.dim()
            shape[dim] = -1

            return segment(x * weight.view(shape), ptr, reduce=reduce)

        return scatter(x * weight, index, dim, dim_size, reduce)

    # Assertions ##############################################################

    def assert_weight_present(self, weight: Optional[Tensor]):
        # TODO Currently, not all aggregators support `ptr`. This assert helps
        # to ensure that we require `weight` to be passed to the computation:
        if weight is None:
            raise NotImplementedError(
                "Weighted aggregation requires 'weight' to be specified")


###############################################################################


def expand_left(ptr: Tensor, dim: int, dims: int) -> Tensor:
    for _ in range(dims + dim if dim < 0 else dim):
        ptr = ptr.unsqueeze(0)
    return ptr
