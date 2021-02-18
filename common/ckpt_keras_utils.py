
"""
CKPT KERAS UTILS

CANDLE checkpoint/restart utilities for Keras

Hyperparameters that affect CANDLE checkpoint/restart:

checksum : boolean
    If True, use checksums on model.h5.
    Default: True.

restart :  "OFF" | "AUTO" | "REQUIRED"
    If AUTO or REQUIRED, automatically try to restart from most recent
    (highest epoch) model.h5.
    REQUIRED will fail if a model cannot be found.
    Default: True

save_best_only : boolean
    If true, only save when save_best_stat has improved.
    Default: False

save_best_stat : string
    Required when save_best_only=True, else unused.
    The stat in logs.model to track for improvement.

skip_epochs : int
    Number of initial epochs to skip before writing checkpoints
    Default: 0

checksum : boolean
    If True, compute a checksum for the model
    and store it in the JSON
    Default: True

metadata : string
    Arbitrary string to add to the JSON file regarding
    job ID, hardware location, etc.
    May be None or an empty string.
    Default: None

clean : boolean
    If True, remove old checkpoints immediately.
    If False, one extra old checkpoint will remain on disk.
    Default: False

Usage:

  Add before training:

    initial_epoch = 0
    J = candle.restart(gParameters, model)
    if J is not None:
        initial_epoch = J['epoch']

  Set up a callback for checkpoints:

    ckpt = candle.CandleCheckpointCallback(gParameters)
    history = model.fit(epochs=gParameters['epochs'],
                        initial_epoch=initial_epoch,
                        ...
                        callbacks=[... , ckpt])
"""

import json
import os
import time

from default_utils import set_up_logger
from keras.callbacks import Callback, ModelCheckpoint

class MultiGPUCheckpoint(ModelCheckpoint):

    def set_model(self, model):
        if isinstance(model.layers[-2], Model):
            self.model = model.layers[-2]
        else:
            self.model = model


class CandleCheckpointCallback(Callback):

    """
    Keras Callback for CANDLE-compliant Benchmarks to use for checkpointing
    Creates a JSON file alongside the weights and optimizer checkpoints
    that includes important metadata, particularly for restarting and
    tracking complex workflows.
    """

    def __init__(self, gParameters, logger="DEFAULT", verbose=True):
        """
        Parameters
        ----------
            logger : Logger
                The logger to use.
                May be None to disable or "DEFAULT" to use the default.
            verbose : boolean
                If True, more verbose logging
                Passed to default_utils.set_up_logger(verbose) for this logger
        """
        import math
        self.logger = logger
        if self.logger == "DEFAULT":
            import logging
            self.logger = logging.getLogger("CandleCheckpointCallback")
            set_up_logger("save/ckpt.log", self.logger, verbose=verbose,
                          fmt_line="%(asctime)s CandleCheckpoint: %(message)s")
        self.scan_params(gParameters)
        self.info("Callback initialized.")
        if self.metadata is not None:
            self.info("metadata='%s'" % self.metadata)
        if self.save_best_only:
            self.info("save_best_stat='%s'" % self.save_best_stat)

    def scan_params(self, gParameters):
        """ Simply translate gParameters into instance fields """
        self.skip_epochs = param(gParameters, "skip_epochs", 0)
        self.save_best_only = param(gParameters, "save_best_only", False)
        self.save_best_stat = param(gParameters, "save_best_stat", 'loss')
        self.best_stat_last = param(gParameters, "best_stat_last", None)
        if self.best_stat_last is None:
            # TODO: Handle positive/negative metrics
            import math
            self.best_stat_last = math.inf
        self.save_weights_only = param(gParameters, "save_weights_only", True)
        self.checksum_enabled = param(gParameters, "checksum", True)
        self.metadata = param(gParameters, "metadata", None)
        self.timestamp_last = param(gParameters, "timestamp_last", None)
        self.clean = param(gParameters, "clean", False)

    def on_epoch_end(self, epoch, logs):
        """
        Normally, ckpt-good is the best saved state.
        When updating:
        1. Write current state to ckpt-work
        2. Rename ckpt-good to ckpt-old
        3. Rename ckpt-work to ckpt-good
        4. Delete ckpt-old
        """
        # print("logs: %s" % str(logs.keys()))
        # TODO: Check save_best_only
        dir_work = "save/ckpt-work"
        dir_good = "save/ckpt-good"
        dir_old  = "save/ckpt-old"
        if not os.path.exists(dir_work):
            os.makedirs(dir_work)
        model_file = dir_work+"/model.h5"
        if not self.save_check(logs, epoch): return
        self.write_model(dir_work, epoch)
        import shutil
        if os.path.exists(dir_old):
            self.debug("removing: '%s'" % dir_old)
            shutil.rmtree(dir_old)
        do_clean = self.clean
        if os.path.exists(dir_good):
            self.debug("renaming: '%s' -> '%s'" % (dir_good, dir_old))
            os.rename(dir_good, dir_old)
        else:
            do_clean = False
        self.debug("renaming: '%s' -> '%s'" % (dir_work, dir_good))
        os.rename(dir_work, dir_good)
        if do_clean:
            self.debug("removing: '%s'" % dir_old)
            shutil.rmtree(dir_old)

    def save_check(self, logs, epoch):
        """
        Make sure we want to save this epoch based on the
        model metrics in given logs
        """
        # skip early epochs to improve speed
        if epoch < self.skip_epochs:
            self.debug("Model saving disabled until epoch %d" % self.skip_epochs)
            return False
        if not self.save_best_only:
            return True # easy- save everything!
        if self.save_best_stat not in logs.keys():
            raise(Exception(("CandleCheckpointCallback: " +
                             "save_best_stat='%s' " +
                             "not in list of model metrics: %s") %
                            (self.save_best_stat, str(logs.keys()))))
        if   logs[self.save_best_stat] < self.best_stat_last:
            symbol =                  "<"
        elif logs[self.save_best_stat] > self.best_stat_last:
            symbol =                  ">"
        else:
            symbol =                  "="
        self.debug("metrics: current=%f %s last=%f" %
                   (logs[self.save_best_stat], symbol, self.best_stat_last))
        if logs[self.save_best_stat] < self.best_stat_last:
            self.best_stat_last = logs[self.save_best_stat]
            return True # model improved- save!
        # else- not saving:
        self.debug("not writing this epoch.")
        return False

    def write_model(self, dir_work, epoch):
        """ Do the I/O, report stats """
        model_file = dir_work + "/model.h5"
        self.debug("writing model to: '%s'" % model_file)
        start = time.time()
        self.model.save(model_file)  # save_format="h5")
        stop = time.time()
        duration = stop - start
        stats = os.stat(model_file)
        MB = stats.st_size / (1024*1024)
        rate = MB / duration
        self.debug("model wrote: %0.3f MB in %0.3f seconds (%0.2f MB/s)." %
                   (MB, duration, rate))
        self.checksum(dir_work)
        self.write_json(dir_work+"/ckpt-info.json", epoch)

    def checksum(self, dir_work):
        """ Simple checksum dispatch """
        if self.checksum_enabled:
            self.cksum_model = checksum_file(self.logger, dir_work+"/model.h5")
        else:
            self.cksum_model = "__DISABLED__"

    def write_json(self, jsonfile, epoch):
        from datetime import datetime
        now = datetime.now()
        D = {}
        D["epoch"] = epoch
        D["save_best_only"] = self.save_best_only
        D["save_best_stat"] = self.save_best_stat
        D["best_stat_last"] = self.best_stat_last
        D["model_file"] = "model.h5"
        D["checksum"] = self.cksum_model
        D["timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
        if self.timestamp_last == None:
            time_elapsed = "__FIRST__"
        else:
            time_elapsed = (now - self.timestamp_last).total_seconds()
        self.timestamp_last = now
        D["time_elapsed"] = time_elapsed
        D["metadata"] = self.metadata
        with open(jsonfile, "w") as fp:
            json.dump(D, fp)
            fp.write("\n")

    def info(self, message):
        if self.logger is not None:
            self.logger.info(message)

    def debug(self, message):
        if self.logger is not None:
            self.logger.debug(message)

def restart(gParameters, model, verbose=True):
    """
    Possibly restarts model from CheckpointCallback according to given
    settings and the ckpt-info.json

    return
           The JSON dict if the restart happened or
           None if the restart did not happen.
    """
    import logging
    logger = logging.getLogger("Candle.restart")
    set_up_logger("save/ckpt.log", logger, verbose=verbose,
                  fmt_line="%(asctime)s CANDLE restart(): %(message)s")

    if disabled(gParameters, "restart"):
        return

    dir_work = "save/ckpt-work"
    dir_good = "save/ckpt-good"
    dir_old  = "save/ckpt-old"
    model_file = dir_good + "/model.h5"
    if not os.path.exists(model_file):
        return None
    logger.info("restarting: " + model_file)
    result = restart_json(gParameters, logger, dir_good)
    logger.info("restarting: epoch=%i timestamp=%s" %
                (result["epoch"], result["timestamp"]))
    start = time.time()
    stats = os.stat(model_file)
    MB = stats.st_size / (1024*1024)
    model.load_weights(model_file)
    stop = time.time()
    duration = stop - start
    rate = MB / duration
    logger.info("model read:  %0.3f MB in %0.3f seconds (%0.2f MB/s)." %
                (MB, duration, rate))
    return result

def restart_json(gParameters, logger, directory):
    json_file = directory + "/ckpt-info.json"
    if not os.path.exists(json_file):
        msg = "restart_json(): in: %s model exists but not json!" % \
              directory
        logger.info(msg)
        if not disabled(gParameters, "require_json"):
            raise Exception(msg)
    with open(json_file) as fp:
        J = json.load(fp)
    print(str(J))

    if not disabled(gParameters, "checksum"):
        checksum = checksum_file(logger, directory + "/model.h5")
        if checksum != J["checksum"]:
            raise Exception("checksum mismatch! directory: " %
                            directory)

    return J


def enabled(gParameters, key):
    """ Is this parameter set to True? """
    return key in gParameters and gParameters[key]


def disabled(gParameters, key):
    """ Is this parameter set to False? """
    return key in gParameters and not gParameters[key]

def param(gParameters, key, dflt):
    if key in gParameters:
        return gParameters[key]
    return dflt

def checksum_file(logger, filename):
    """ Read file, compute checksum, return it as a string. """
    import zlib
    start = time.time()
    chunk_size = 10*1024*1024
    total = 0
    with open(filename, "rb") as fp:
        checksum = 0
        while True:
            chunk = fp.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            checksum = zlib.crc32(chunk, checksum)
    stop = time.time()
    MB = total / (1024*1024)
    duration = stop - start
    rate = MB / duration
    logger.info("checksummed: %0.3f MB in %.3f seconds (%.2f MB/s)." %
                (MB, duration, rate))
    return str(checksum)
