#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import inspect
import autopath

from alex.components.slu.base import SLUInterface, SLUPreprocessing, \
                                     CategoryLabelDatabase
from alex.components.slu.exception import SLUException
from alex.components.slu.dailrclassifier import DAILogRegClassifier


def get_slu_type(cfg):
    """Get SLU type from the configuration."""
    return cfg['SLU']['type']


def slu_factory(slu_type, cfg):
    cldb = CategoryLabelDatabase(cfg['SLU']['cldb'])

    preprocessing_cls = cfg['SLU'].get('preprocessing_cls', SLUPreprocessing)
    preprocessing = preprocessing_cls(cldb)

    if inspect.isclass(slu_type) and issubclass(slu_type, SLUInterface):
        slu = slu_type(preprocessing, cfg=cfg)
        return slu
    if slu_type == 'DAILogRegClassifier':
        slu = DAILogRegClassifier(preprocessing)
        slu.load_model(
            cfg['SLU']['DAILogRegClassifier']['model'])

        return slu
    else:
        raise SLUException('Unsupported spoken language understanding: {type_}'\
            .format(type_=cfg['SLU']['type']))
