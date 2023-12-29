# Copyright 2023 The TensorFlow Authors. All Rights Reserved.
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

"""Tests for label_mean."""

from absl.testing import parameterized
import numpy as np
import tensorflow as tf, tf_keras
from official.recommendation.uplift import keras_test_case
from official.recommendation.uplift import types
from official.recommendation.uplift.metrics import label_mean


class LabelMeanTest(keras_test_case.KerasTestCase, parameterized.TestCase):

  def _get_y_pred(
      self, is_treatment: tf.Tensor
  ) -> types.TwoTowerTrainingOutputs:
    # All tensors except the is_treatment tensor is distracting from the
    # testing logic.
    return types.TwoTowerTrainingOutputs(
        shared_embedding=tf.ones_like(is_treatment),
        control_predictions=tf.ones_like(is_treatment),
        treatment_predictions=tf.ones_like(is_treatment),
        uplift=tf.ones_like(is_treatment),
        control_logits=tf.ones_like(is_treatment),
        treatment_logits=tf.ones_like(is_treatment),
        true_logits=tf.ones_like(is_treatment),
        is_treatment=is_treatment,
    )

  @parameterized.named_parameters(
      {
          "testcase_name": "unweighted",
          "y_true": tf.constant([0, 1, 5, 6]),
          "is_treatment": tf.constant([[True], [False], [True], [False]]),
          "sample_weight": None,
          "expected_result": {
              "label/mean": 3.0,
              "label/mean/control": 3.5,
              "label/mean/treatment": 2.5,
          },
      },
      {
          "testcase_name": "weighted",
          "y_true": tf.constant([0, 1, 5, 6, -7]),
          "is_treatment": tf.constant(
              [[True], [False], [True], [True], [False]]
          ),
          "sample_weight": tf.constant([0.5, 0.5, 0, 0.7, 1.8]),
          "expected_result": {
              "label/mean": np.average(
                  np.array([0, 1, 5, 6, -7]),
                  weights=np.array([0.5, 0.5, 0, 0.7, 1.8]),
              ),
              "label/mean/control": np.average(
                  np.array([1, -7]), weights=np.array([0.5, 1.8])
              ),
              "label/mean/treatment": np.average(
                  np.array([0, 5, 6]), weights=np.array([0.5, 0, 0.7])
              ),
          },
      },
      {
          "testcase_name": "only_control",
          "y_true": tf.constant([[0], [1], [5]]),
          "is_treatment": tf.constant([[False], [False], [False]]),
          "sample_weight": tf.constant([1, 0, 1]),
          "expected_result": {
              "label/mean": 2.5,
              "label/mean/control": 2.5,
              "label/mean/treatment": 0.0,
          },
      },
      {
          "testcase_name": "only_treatment",
          "y_true": tf.constant([[0], [1], [5]]),
          "is_treatment": tf.constant([[True], [True], [True]]),
          "sample_weight": tf.constant([0, 1, 1]),
          "expected_result": {
              "label/mean": 3.0,
              "label/mean/control": 0.0,
              "label/mean/treatment": 3.0,
          },
      },
      {
          "testcase_name": "one_entry",
          "y_true": tf.constant([2.5]),
          "is_treatment": tf.constant([True]),
          "sample_weight": tf.constant([1]),
          "expected_result": {
              "label/mean": 2.5,
              "label/mean/control": 0.0,
              "label/mean/treatment": 2.5,
          },
      },
      {
          "testcase_name": "no_entry",
          "y_true": tf.constant([]),
          "is_treatment": tf.constant([], dtype=tf.bool),
          "sample_weight": tf.constant([]),
          "expected_result": {
              "label/mean": 0.0,
              "label/mean/control": 0.0,
              "label/mean/treatment": 0.0,
          },
      },
  )
  def test_treatment_sliced_metric(
      self, y_true, is_treatment, sample_weight, expected_result
  ):
    metric = label_mean.LabelMean()
    y_pred = self._get_y_pred(is_treatment)
    metric(y_true, y_pred, sample_weight=sample_weight)
    self.assertEqual(expected_result, metric.result())

  def test_multiple_batches(self):
    metric = label_mean.LabelMean(name="label")

    metric.update_state(
        y_true=tf.constant([[1], [2], [4]]),
        y_pred=self._get_y_pred(tf.constant([[True], [True], [True]])),
        sample_weight=None,
    )
    metric.update_state(
        y_true=tf.constant([[-3], [0], [5]]),
        y_pred=self._get_y_pred(tf.constant([[False], [False], [False]])),
        sample_weight=None,
    )
    metric.update_state(
        y_true=tf.constant([[0], [1], [-5]]),
        y_pred=self._get_y_pred(tf.constant([[True], [False], [True]])),
        sample_weight=tf.constant([0.3, 0.25, 0.7]),
    )

    expected_results = {
        "label": np.average(
            np.array([1, 2, 4, -3, 0, 5, 0, 1, -5]),
            weights=np.array([1, 1, 1, 1, 1, 1, 0.3, 0.25, 0.7]),
        ),
        "label/control": np.average(
            np.array([-3, 0, 5, 1]), weights=np.array([1, 1, 1, 0.25])
        ),
        "label/treatment": np.average(
            np.array([1, 2, 4, 0, -5]), weights=np.array([1, 1, 1, 0.3, 0.7])
        ),
    }
    self.assertEqual(expected_results, metric.result())

  def test_metric_states(self):
    metric = label_mean.LabelMean()

    expected_initial_result = {
        "label/mean": 0.0,
        "label/mean/control": 0.0,
        "label/mean/treatment": 0.0,
    }
    self.assertEqual(expected_initial_result, metric.result())

    metric(
        y_true=tf.constant([1, 2, 6]),
        y_pred=self._get_y_pred(tf.constant([[True], [False], [True]])),
    )
    self.assertEqual(
        {
            "label/mean": 3.0,
            "label/mean/control": 2.0,
            "label/mean/treatment": 3.5,
        },
        metric.result(),
    )

    metric.reset_states()
    self.assertEqual(expected_initial_result, metric.result())

  def test_metric_config(self):
    metric = label_mean.LabelMean(name="test_name", dtype=tf.float16)
    y_true = tf.constant([[1], [2], [3], [4]])
    y_pred = self._get_y_pred(
        is_treatment=tf.constant([[True], [False], [True], [False]]),
    )
    self.assertLayerConfigurable(layer=metric, y_true=y_true, y_pred=y_pred)

  def test_invalid_prediction_tensor_type(self):
    metric = label_mean.LabelMean()

    with self.assertRaisesRegex(
        TypeError, "y_pred must be of type `TwoTowerTrainingOutputs`"
    ):
      metric.update_state(y_true=tf.ones((3, 1)), y_pred=tf.ones((3, 1)))


if __name__ == "__main__":
  tf.test.main()
