from .base import Aggregation, WeightedAggregation
from .multi import MultiAggregation
from .basic import (
    MeanAggregation,
    WeightedMeanAggregation,
    SumAggregation,
    MaxAggregation,
    MinAggregation,
    MulAggregation,
    VarAggregation,
    StdAggregation,
    SoftmaxAggregation,
    PowerMeanAggregation,
)
from .quantile import MedianAggregation, QuantileAggregation
from .lstm import LSTMAggregation
from .gru import GRUAggregation
from .set2set import Set2Set
from .scaler import DegreeScalerAggregation
from .equilibrium import EquilibriumAggregation
from .sort import SortAggregation
from .gmt import GraphMultisetTransformer
from .attention import AttentionalAggregation
from .mlp import MLPAggregation
from .deep_sets import DeepSetsAggregation
from .set_transformer import SetTransformerAggregation
from .soft_median import (
    WeightedMedianAggregation,
    WeightedQuantileAggregation,
    SoftMedianAggregation,
)
from .lcm import LCMAggregation

__all__ = classes = [
    'Aggregation',
    'MultiAggregation',
    'WeightedAggregation',
    'SumAggregation',
    'MeanAggregation',
    'WeightedMeanAggregation',
    'MaxAggregation',
    'MinAggregation',
    'MulAggregation',
    'VarAggregation',
    'StdAggregation',
    'SoftmaxAggregation',
    'PowerMeanAggregation',
    'MedianAggregation',
    'QuantileAggregation',
    'LSTMAggregation',
    'GRUAggregation',
    'Set2Set',
    'DegreeScalerAggregation',
    'SortAggregation',
    'GraphMultisetTransformer',
    'AttentionalAggregation',
    'EquilibriumAggregation',
    'MLPAggregation',
    'DeepSetsAggregation',
    'SetTransformerAggregation',
    'WeightedMedianAggregation',
    'WeightedQuantileAggregation',
    'SoftMedianAggregation',
    'LCMAggregation',
]
