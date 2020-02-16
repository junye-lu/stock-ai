#!/usr/bin/env python3
'''
@暂时可遗弃
回测机器学习框架用的，用于测试动态调整参数矩阵的想法
'''
import pandas as pd
import numpy as np
import argparse, datetime
import sys
import multiprocessing as mp
from lib.datasource import DataSource as ds
from lib.feature_extract import featureExtractor as fe
from lib.backtest import backtest as bt
from lib.strategy import strategy as stg
from lib.learn import learn as ln

def init_globals(arg1, arg2):
    global start_ts, counter, total
    start_ts = datetime.datetime.now(tz=None)
    counter,total = arg1,arg2
    return

def preload_data(data):
    symbol, start_date, end_date = data[0], data[1].start_date, data[1].end_date
    dataset = ds.loadFeaturedData(symbol, start_date, end_date)
    # time.sleep(0.1)
    # 观察数据
    with counter.get_lock():
        counter.value +=1
        progress = counter.value / total
        time_elapsed = datetime.datetime.now(tz=None) - start_ts
        time_eta = (time_elapsed/progress) * (1 - progress)
        bar_width = 25
        print("\rProgress: {:>5.2f}% ({:04d}/{:04d}) Symbol: {:s}\t[{}{}]\tElapsed Time: {}  ETA: {}".format(
            round(progress*100,2), counter.value, total, symbol,
            "#"*int(progress*bar_width),"."*(bar_width-int(progress*bar_width)),
            str(time_elapsed).split(".")[0], str(time_eta).split(".")[0]
        ), end="")
    return

if __name__ == "__main__":
    mp.freeze_support()

    parser = argparse.ArgumentParser(description='Machine Learning.')
    parser.add_argument('--batch-size',
                        default=100, type=int,
                        help='how many batch of samples for learning')

    parser.add_argument('--skip-batch',
                        default=0, type=int,
                        help='skip first N of batch')

    parser.add_argument('--step-size',
                        default=30, type=int,
                        help='how many generations for each batch of learning')

    parser.add_argument('--training-set-size',
                        default=10, type=int,
                        help='how many data samples for each batch of learning')

    parser.add_argument('--early-stop',
                        default=3, type=int,
                        help='Stop learning if N batch of improving the result')

    args = vars(parser.parse_args())

    import warnings
    warnings.simplefilter(action='ignore', category=FutureWarning)


    np.random.seed(0)
    securities = ds.loadSecuirtyList();

    for i in range(args['batch_size']):
        #skip batch logic
        if i < args['skip_batch']: continue

        print("Learning batch :{}".format(i))

        print("Preloading datasets: {}".format(args['training_set_size']*2))
        processed_counter = mp.Value('i',0)
        pool = mp.Pool(min(args['training_set_size'],mp.cpu_count()), initializer=init_globals, initargs=(processed_counter, args['training_set_size']*2))

        # prepare datasets
        training_sets = []
        samples = securities.sample(args['training_set_size']*2)
        res = pool.map(preload_data, samples.iterrows())
        pool.close()
        print("[DONE]")

        print("Generating training sets:\t",end="")
        for symbol,sample in samples[:(args['training_set_size']+1)].iterrows():
            start_date, end_date = sample.start_date, sample.end_date
            dataset = ds.loadFeaturedData(symbol, start_date, end_date)
            if dataset.shape[0]>0: training_sets.append(dataset)
        print("[DONE]")

        print("Generating validation sets:\t",end="")
        validation_sets = []
        for symbol,sample in samples[args['training_set_size']:].iterrows():
            start_date, end_date = sample.start_date, sample.end_date
            dataset = ds.loadFeaturedData(symbol, start_date, end_date)
            if dataset.shape[0]>0: validation_sets.append(dataset)
        print("[DONE]")

        ml = ln()
        last_score = 0
        stop_improving_counter = 0
        for _ in range(args['step_size']):
            print("Batch :{}\t GA Learning step: {}".format(i,_))
            report = ml.evolve(training_sets=training_sets, validation_sets=validation_sets)

            # early stop logic
            if report['validation_score'] == last_score:
                stop_improving_counter+=1
                print("Not improving result: {}".format(stop_improving_counter))
            if stop_improving_counter>=args['early_stop']:
                print("Early stop learning")
                break
            last_score = report['validation_score']

            print(report)
        ml.save()
        del ml

        print("-"*100)
        print("\n")
