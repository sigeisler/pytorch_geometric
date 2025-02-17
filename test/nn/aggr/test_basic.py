import pytest
import torch

import torch_geometric.typing
from torch_geometric.nn import (
    MaxAggregation,
    MeanAggregation,
    MinAggregation,
    MulAggregation,
    PowerMeanAggregation,
    SoftmaxAggregation,
    StdAggregation,
    SumAggregation,
    VarAggregation,
    WeightedMeanAggregation,
)


def test_validate():
    x = torch.randn(6, 16)
    index = torch.tensor([0, 0, 1, 1, 1, 2])
    ptr = torch.tensor([0, 2, 5, 6])

    aggr = MeanAggregation()

    with pytest.raises(ValueError, match="invalid dimension"):
        aggr(x, index, dim=-3)

    with pytest.raises(ValueError, match="invalid 'dim_size'"):
        aggr(x, ptr=ptr, dim_size=2)

    with pytest.raises(ValueError, match="invalid 'dim_size'"):
        aggr(x, index, dim_size=2)


def test_weighted_validate():
    x = torch.randn(6, 16)
    index = torch.tensor([0, 0, 1, 1, 1, 2])

    aggr = WeightedMeanAggregation()

    with pytest.raises(ValueError, match="needs to be one-dimensional"):
        weight = torch.rand(6, 2)
        aggr(x, index, weight)

    with pytest.raises(ValueError, match="that the size of the inputs align"):
        weight = torch.rand(4)
        aggr(x, index, weight)


@pytest.mark.parametrize('Aggregation', [
    MeanAggregation,
    SumAggregation,
    MaxAggregation,
    MinAggregation,
    MulAggregation,
    VarAggregation,
    StdAggregation,
])
def test_basic_aggregation(Aggregation):
    x = torch.randn(6, 16)
    index = torch.tensor([0, 0, 1, 1, 1, 2])
    ptr = torch.tensor([0, 2, 5, 6])

    aggr = Aggregation()
    assert str(aggr) == f'{Aggregation.__name__}()'

    out = aggr(x, index)
    assert out.size() == (3, x.size(1))

    if isinstance(aggr, MulAggregation):
        with pytest.raises(NotImplementedError, match="requires 'index'"):
            aggr(x, ptr=ptr)
    elif not torch_geometric.typing.WITH_TORCH_SCATTER:
        with pytest.raises(ImportError, match="'segment' requires"):
            aggr(x, ptr=ptr)
    else:
        assert torch.allclose(out, aggr(x, ptr=ptr))


def test_weighted_mean_aggregation():
    x = torch.randn(6, 16)
    weight = torch.rand(6)
    index = torch.tensor([0, 0, 1, 1, 1, 2])
    ptr = torch.tensor([0, 2, 5, 6])

    expected = torch.cat([
        (x[0:2] * weight[0:2].view(-1, 1)).sum(dim=0, keepdim=True),
        (x[2:5] * weight[2:5].view(-1, 1)).sum(dim=0, keepdim=True),
        (x[5:6] * weight[5:6].view(-1, 1)).sum(dim=0, keepdim=True),
    ], dim=0)

    aggr = WeightedMeanAggregation()
    assert str(aggr) == 'WeightedMeanAggregation()'

    out = aggr(x, index, weight)
    assert out.size() == (3, x.size(1))
    assert torch.allclose(out, expected)
    if torch_geometric.typing.WITH_TORCH_SCATTER:
        assert torch.allclose(out, aggr(x, weight=weight, ptr=ptr))


def test_var_aggregation():
    x = torch.randn(6, 16)
    index = torch.tensor([0, 0, 1, 1, 1, 2])

    var_aggr = VarAggregation()
    out = var_aggr(x, index)

    mean_aggr = MeanAggregation()
    expected = mean_aggr((x - mean_aggr(x, index)[index]).pow(2), index)
    assert torch.allclose(out, expected, atol=1e-6)


def test_empty_std_aggregation():
    aggr = StdAggregation()

    x = torch.empty(0, 6).reshape(0, 6)
    index = torch.empty(0, dtype=torch.long)

    out = aggr(x, index, dim_size=5)
    assert out.size() == (5, 6)
    assert float(out.abs().sum()) == 0.0


@pytest.mark.parametrize('Aggregation', [
    SoftmaxAggregation,
    PowerMeanAggregation,
])
@pytest.mark.parametrize('learn', [True, False])
def test_learnable_aggregation(Aggregation, learn):
    x = torch.randn(6, 16)
    index = torch.tensor([0, 0, 1, 1, 1, 2])
    ptr = torch.tensor([0, 2, 5, 6])

    aggr = Aggregation(learn=learn)
    assert str(aggr) == f'{Aggregation.__name__}(learn={learn})'

    out = aggr(x, index)
    assert out.size() == (3, x.size(1))

    if not torch_geometric.typing.WITH_TORCH_SCATTER:
        with pytest.raises(ImportError, match="'segment' requires"):
            aggr(x, ptr=ptr)
    else:
        assert torch.allclose(out, aggr(x, ptr=ptr))

    if learn:
        out.mean().backward()
        for param in aggr.parameters():
            assert not torch.isnan(param.grad).any()


@pytest.mark.parametrize('Aggregation', [
    SoftmaxAggregation,
    PowerMeanAggregation,
])
def test_learnable_channels_aggregation(Aggregation):
    x = torch.randn(6, 16)
    index = torch.tensor([0, 0, 1, 1, 1, 2])
    ptr = torch.tensor([0, 2, 5, 6])

    aggr = Aggregation(learn=True, channels=16)
    assert str(aggr) == f'{Aggregation.__name__}(learn=True)'

    out = aggr(x, index)
    assert out.size() == (3, x.size(1))

    if not torch_geometric.typing.WITH_TORCH_SCATTER:
        with pytest.raises(ImportError, match="'segment' requires"):
            aggr(x, ptr=ptr)
    else:
        assert torch.allclose(out, aggr(x, ptr=ptr))

    out.mean().backward()
    for param in aggr.parameters():
        assert not torch.isnan(param.grad).any()
