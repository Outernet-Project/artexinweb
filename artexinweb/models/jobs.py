# -*- coding: utf-8 -*-
import datetime
import os

import mongoengine

from artexinweb import worker, utils, settings


MD5_LENGTH = 32


class Task(mongoengine.Document):
    """Tasks are the smallest unit of work, which contain an exact target that
    needs to be processed."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"
    FINISHED = "FINISHED"
    STATUSES = (
        (QUEUED, "Queued"),
        (PROCESSING, "Processing"),
        (FAILED, "Failed"),
        (FINISHED, "Finished"),
    )

    meta = {
        'indexes': ['md5']
    }

    job_id = mongoengine.StringField(required=True,
                                     max_length=MD5_LENGTH,
                                     min_length=MD5_LENGTH,
                                     help_text="ID of parent Job.")
    target = mongoengine.StringField(required=True,
                                     help_text="Target URL or filesystem path")
    md5 = mongoengine.StringField(max_length=MD5_LENGTH,
                                  min_length=MD5_LENGTH,
                                  help_text="MD5 hexdigest of target.")
    title = mongoengine.StringField(help_text="Processed page title.")
    size = mongoengine.IntField(min_value=0,
                                help_text="Size of page in bytes.")
    images = mongoengine.IntField(min_value=0,
                                  help_text="Number of images on the page.")
    timestamp = mongoengine.DateTimeField(help_text="End time of task.")
    status = mongoengine.StringField(choices=STATUSES,
                                     default=QUEUED,
                                     help_text="Job status.")
    notes = mongoengine.StringField(help_text="Arbitary information")

    @classmethod
    def create(cls, job_id, target):
        """Create a new task for the passed in target.

        :param job_id:  The string ID of the parent job instance
        :param target:  The target URL or filesystem path
        :returns:       ``Task`` instance
        """
        task = cls(job_id=job_id, target=target)
        task.save()
        return task

    @property
    def is_queued(self):
        return self.status == self.QUEUED

    @property
    def is_processing(self):
        return self.status == self.PROCESSING

    @property
    def is_finished(self):
        return self.status == self.FINISHED

    @property
    def is_failed(self):
        return self.status == self.FAILED

    @property
    def download_link(self):
        url_template = settings.BOTTLE_CONFIG['artexin.zipball_url_template']
        return url_template.format(self.md5)

    @property
    def zipball_path(self):
        zipball_root = settings.BOTTLE_CONFIG['artexin.out_dir']
        filename = '{0}.zip'.format(self.md5)
        return os.path.join(zipball_root, filename)

    def mark_queued(self):
        self.status = self.QUEUED
        self.save()

    def mark_processing(self):
        self.status = self.PROCESSING
        self.save()

    def mark_failed(self, reason):
        self.status = self.FAILED
        self.notes = reason
        self.save()

    def mark_finished(self):
        self.status = self.FINISHED
        self.notes = ''
        self.save()


class Job(mongoengine.Document):
    """Jobs are container units, holding one or more tasks."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    ERRED = "ERRED"
    FINISHED = "FINISHED"
    STATUSES = (
        (QUEUED, "Queued"),
        (PROCESSING, "Processing"),
        (ERRED, "Erred"),
        (FINISHED, "Finished"),
    )

    STANDALONE = "STANDALONE"
    FETCHABLE = "FETCHABLE"
    TYPES = (
        (STANDALONE, "Standalone"),
        (FETCHABLE, "Fetchable")
    )

    job_id = mongoengine.StringField(required=True,
                                     primary_key=True,
                                     max_length=MD5_LENGTH,
                                     min_length=MD5_LENGTH)
    status = mongoengine.StringField(choices=STATUSES,
                                     required=True,
                                     default=QUEUED,
                                     help_text="Job status.")
    job_type = mongoengine.StringField(choices=TYPES,
                                       required=True,
                                       help_text="Job type.")
    scheduled = mongoengine.DateTimeField(required=True,
                                          help_text="Start time of the job.")
    updated = mongoengine.DateTimeField(required=True,
                                        help_text="Time of last status update")
    tasks = mongoengine.ListField(mongoengine.ReferenceField(Task),
                                  required=True,
                                  help_text="References to subtasks of job.")
    options = mongoengine.DictField(help_text="Additional(free-form) options.")

    @property
    def is_queued(self):
        return self.status == self.QUEUED

    @property
    def is_processing(self):
        return self.status == self.PROCESSING

    @property
    def is_finished(self):
        return self.status == self.FINISHED

    @property
    def is_erred(self):
        return self.status == self.ERRED

    def save(self, *args, **kwargs):
        if not self.updated:
            # on creation, the updated field should be the same as scheduled
            self.updated = self.scheduled
        else:
            # on subsequent saves, update the updated field
            self.updated = datetime.datetime.utcnow()

        return super(Job, self).save(*args, **kwargs)

    @classmethod
    def generate_id(cls, *args):
        """Generate a unique job_id by feeding the hash object with the passed
        in arguments."""
        return utils.hash_data(*args)

    @classmethod
    def create(cls, targets, job_type, **kwargs):
        """Create a new job from the passed in list of target(s).

        :param targets:  Iterable containing URLs or filesystem paths
        :param kwargs:   All kwargs are stored as additional options of the job
        :returns:       ``Job`` instance
        """
        creation_time = datetime.datetime.utcnow()

        # generate job_id from the current time + the passed in targets
        job_id = cls.generate_id(creation_time, *list(targets))

        job = cls(job_id=job_id,
                  job_type=job_type,
                  scheduled=creation_time,
                  options=kwargs)

        job.tasks = [Task.create(job_id, t) for t in targets]
        job.save()
        job.schedule()

        return job

    @classmethod
    def is_valid_type(cls, job_type):
        """Check whether the passed in job type is a valid one.

        :param job_type:  A job type code(string)"""
        codes, _ = zip(*cls.TYPES)
        return job_type in codes

    def schedule(self):
        """Schedule the job for processing by a background worker."""
        worker.dispatch({'type': self.job_type, 'id': self.job_id})

    def retry(self):
        """Retry a previously failed job."""
        self.mark_queued()
        self.schedule()

    def mark_queued(self):
        self.status = self.QUEUED
        self.save()

    def mark_processing(self):
        self.status = self.PROCESSING
        self.save()

    def mark_erred(self):
        self.status = self.ERRED
        self.save()

    def mark_finished(self):
        self.status = self.FINISHED
        self.save()
