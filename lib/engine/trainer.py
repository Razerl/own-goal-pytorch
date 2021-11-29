import torch
import time
import datetime
import math
import sys
from lib.utils.metric_logger import MetricLogger
from lib.utils.eval_utils import accuracy


def train(cfg, model, criterion, data_loader, optimizer, epoch,
          logger, scheduler=None):
    logger.info("Start training ... ")
    meters = MetricLogger(delimiter="  ")
    max_iter = len(data_loader)
    print_freq = cfg.trainig.training_print_freq
    num_class = cfg.model.num_class
    max_norm = cfg.trainig.max_norm

    start_training_time = time.time()
    end = time.time()
    for iteration, (inputs, enc_target, distance_target, class_h_target, dec_target) in enumerate(data_loader):
        data_time = time.time() - end
        inputs = inputs.cuda()
        class_h_target = class_h_target.cuda()
        dec_target = dec_target.cuda()

        enc_score_p0, dec_scores = model(inputs)

        outputs = {
            'labels_encoder': enc_score_p0,  # [128, 17]
            'labels_decoder': dec_scores.view(-1, num_class),  # [128, 8, 17]
        }
        targets = {
            'labels_encoder': class_h_target.view(-1, num_class),
            'labels_decoder': dec_target.view(-1, num_class),
        }
        prec1, prec5 = accuracy(enc_score_p0.data, torch.argmax(class_h_target, dim=1), topk=(1, 5))
        loss_dict = criterion(outputs, targets)
        weight_dict = criterion.weight_dict
        losses = sum(loss_dict[k] * weight_dict[k] for k in loss_dict.keys() if k in weight_dict)
        loss_value = losses.item()

        if not math.isfinite(loss_value):
            logger.info("Loss is {}, stopping training".format(loss_value))
            logger.info(loss_dict)
            sys.exit(1)

        meters.update(losses=loss_value, **loss_dict)
        meters.update(top1=prec1, top5=prec5)

        optimizer.zero_grad()
        losses.backward()
        if max_norm > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm)
        optimizer.step()
        scheduler.step()

        batch_time = time.time() - end
        end = time.time()
        meters.update(time=batch_time, data=data_time)

        eta_seconds = meters.time.global_avg * (max_iter - iteration)
        eta_string = str(datetime.timedelta(seconds=int(eta_seconds)))

        if iteration % print_freq == 0 or iteration == max_iter - 1:
            logger.info(
                meters.delimiter.join(
                    [
                        "epoch: {epoch}",
                        "iter: {iter}/{total}",
                        "eta: {eta}}",
                        "{meters}",
                        "lr: {lr:.6f}",
                    ]
                ).format(
                    epoch=epoch,
                    eta=eta_string,
                    iter=iteration,
                    total=max_iter,
                    meters=str(meters),
                    lr=optimizer.param_groups[0]["lr"],
                )
            )
    total_training_time = time.time() - start_training_time
    total_time_str = str(datetime.timedelta(seconds=total_training_time))
    logger.info(
        "Total training time: {} ({:.4f} s / it)".format(
            total_time_str, total_training_time / max_iter
        )
    )
    return meters
