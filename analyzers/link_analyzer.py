import pandas as pd


def read_capacity(file):
    return pd.read_csv(
        file,
        index_col=0,
        names=['time', 'bandwidth'],
        header=None,
        usecols=[0, 2],
    )


class LinkAnalyzer():
    def __init__(self, basetime):
        self._basetime = basetime

    def set_basetime(self, df):
        if not self._basetime:
            self._basetime = df.index[0]
        df.index = pd.to_datetime(df.index - self._basetime, unit='ms')
        return df

    def add_capacity(self, file):
        df = read_capacity(file)
        self._capacity = self.set_basetime(df)

    def plot_capacity(self, ax, params={}):
        defaults = {
                'linewidth': 0.5,
                'label': 'Capacity',
                }
        p = defaults | params
        out, = ax.step(
                self._capacity.index,
                self._capacity.values,
                where='post',
                **p)
        return out
