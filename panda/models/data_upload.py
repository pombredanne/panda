#!/usr/bin/env python

import os.path

from django.conf import settings
from django.db import models

from panda import utils
from panda.exceptions import DataUploadNotDeletable
from panda.fields import JSONField
from panda.models.base_upload import BaseUpload
from panda.tasks import PurgeDataTask

class DataUpload(BaseUpload):
    """
    A data file uploaded to PANDA (either a table or metadata file).
    """
    from panda.models.dataset import Dataset

    dataset = models.ForeignKey(Dataset, related_name='data_uploads', null=True,
        help_text='The dataset this upload is associated with.')

    data_type = models.CharField(max_length=4, null=True, blank=True,
        help_text='The type of this file, if known.')
    encoding = models.CharField(max_length=32, default='utf-8',
        help_text='The character encoding of this file. Defaults to utf-8')
    dialect = JSONField(null=True,
        help_text='Description of the formatting of this file.')
    columns = JSONField(null=True,
        help_text='An list of names for this uploads columns.')
    sample_data = JSONField(null=True,
        help_text='Example data from this file.')
    guessed_types = JSONField(null=True,
        help_text='Column types guessed based on a sample of data.')
    imported = models.BooleanField(default=False,
        help_text='Has this upload ever been imported into its parent dataset.')
    deletable = models.BooleanField(default=True,
        help_text='Can this data upload be deleted? False for uploads prior to 1.0.')
    
    file_root = settings.MEDIA_ROOT

    class Meta:
        app_label = 'panda'
        ordering = ['creation_date']

    def __unicode__(self):
        return self.filename

    def save(self, *args, **kwargs):
        if self.data_type is None:
            self.data_type = self._infer_data_type()

        if self.data_type:
            path = self.get_path()

            if self.dialect is None:
                self.dialect = utils.sniff_dialect(self.data_type, path, encoding=self.encoding)

            if self.columns is None:
                self.columns = utils.extract_column_names(self.data_type, path, self.dialect_as_parameters(), encoding=self.encoding)

            if self.sample_data is None:
                self.sample_data = utils.sample_data(self.data_type, path, self.dialect_as_parameters(), encoding=self.encoding)

            if self.guessed_types is None:
                self.guessed_types = utils.guess_column_types(self.data_type, path, self.dialect_as_parameters(), encoding=self.encoding)

        super(DataUpload, self).save(*args, **kwargs)

    def _infer_data_type(self):
        """
        Get the data type of this file. Returns an empty string
        if the file is not a recognized type.
        """
        extension = os.path.splitext(self.filename)[1]

        if extension == '.csv':
            return 'csv' 
        elif extension == '.xls':
            return 'xls'
        elif extension == '.xlsx':
            return 'xlsx'

        return ''

    def dialect_as_parameters(self):
        """
        Dialect parameters are stored as a JSON document, which causes
        certain characters to be escaped. This method reverses this so
        they can be used as arguments.
        """
        dialect_params = {}

        # This code is absolutely terrifying
        # (Also, it works.)
        for k, v in self.dialect.items():
            if isinstance(v, basestring):
                dialect_params[k] = v.decode('string_escape')
            else:
                dialect_params[k] = v

        return dialect_params

    def delete(self, *args, **kwargs):
        """
        Cancel any in progress task.
        """
        skip_purge = kwargs.pop('skip_purge', False)
        force = kwargs.pop('force', False)

        # Don't allow deletion of dated uploads unless forced
        if not self.deletable and not force:
            raise DataUploadNotDeletable('This data upload was created before deleting individual data uploads was supported. In order to delete it you must delete the entire dataset.')

        # Update related datasets so deletes will not cascade
        if self.initial_upload_for.count():
            for dataset in self.initial_upload_for.all():
                dataset.initial_upload = None
                dataset.save()

        # Cleanup data in Solr
        if self.dataset and self.imported and not skip_purge:
            PurgeDataTask.apply_async(args=[self.dataset.slug, self.id])

        super(DataUpload, self).delete(*args, **kwargs)

