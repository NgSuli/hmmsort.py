import sys
import os
import scipy.io as mio
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import (QMainWindow, QApplication, QWidget,
                             QVBoxLayout, QPushButton, QInputDialog, QMessageBox)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)

import glob
import h5py
import numpy as np

picked_lines = []

scriptDir = os.path.dirname(os.path.realpath(__file__))


class SaveFile():
    def __init__(self, fname):
        self.fname = fname
        self.ishdf5 = False

    def __enter__(self):
        if h5py.is_hdf5(self.fname):
            self.ishdf5 = True
            self.ff = h5py.File(self.fname, "r")
        else:
            self.ff = mio.loadmat(self.fname)
        return self.ff

    def __exit__(self, type, value, traceback):
        if self.ishdf5:
            try:
                self.ff.close()
            except:
                pass


class SimplerToolbar(NavigationToolbar):
    toolitems = [t for t in NavigationToolbar.toolitems if
                 t[0] in ("Home", "Pan", "Zoom")]

    def __init__(self, *args, **kwargs):
        super(SimplerToolbar, self).__init__(*args, **kwargs)
        self.spiketrain_button = QPushButton()
        pm = QPixmap(scriptDir + os.path.sep + "/spiketrain_button.png")
        if hasattr(pm, 'setDevicePixelRatio'):
            pm.setDevicePixelRatio(self.canvas._dpi_ratio)
        self.spiketrain_button.setIcon(QIcon(pm))
        self.spiketrain_button.setFixedSize(24, 24)
        self.spiketrain_button.setToolTip("Create spike trains from selected templates")
        self.addWidget(self.spiketrain_button)


class ViewWidget(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.mainWidget = QWidget()
        self.setCentralWidget(self.mainWidget)
        layout = QVBoxLayout()
        self.mainWidget.setLayout(layout)

        self.figure_canvas = FigureCanvas(Figure())
        self.navigation_toolbar = SimplerToolbar(self.figure_canvas, self,
                                                 coordinates=False)  # turn off coordinates
        self.navigation_toolbar.spiketrain_button.clicked.connect(self.save_spiketrains)
        layout.addWidget(self.navigation_toolbar, 0)
        layout.addWidget(self.figure_canvas, 10)
        self.figure = self.figure_canvas.figure
        self.figure.canvas.mpl_connect('pick_event', self.pick_event)
        ax = self.figure.add_subplot(111)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_xlabel("State")
        ax.set_ylabel("Amplitude")

        self.picked_lines = []
        self.sampling_rate = -1.0

    def pick_event(self, event):
        artist = event.artist
        lw = artist.get_linewidth()
        label = artist.get_label()
        if lw == 1.5:
            artist.set_linewidth(2*lw)
            self.picked_lines.append(label)
        elif lw > 1.5:
            artist.set_linewidth(lw/2)
            self.picked_lines.remove(label)
        artist.figure.canvas.draw()

    def plot_waveforms(self, waveforms, pp):
        ax = self.figure.axes[0]
        for i in xrange(waveforms.shape[0]):
            ax.plot(waveforms[i, 0, :], label="Waveform %d" % (i, ), picker=5)
        ax.legend()

    def save_spiketrains(self):
        print "Saving spiketrains"
        with SaveFile(self.sortfile) as qq:
            if ("samplingRate" not in qq.keys()) and ("samplingrate" not in qq.keys()):
                if self.sampling_rate == -1.0:
                    text, ok = QInputDialog.getText(self, 'Sampling rate',
                                                          'Sampling rate [Hz] :')
                    if ok:
                        self.sampling_rate = float(text)
                    else:
                        return  # not able to continue with a sampling rate
            else:
                self.sampling_rate = qq.get("samplingRate",qq.get("samplingrate", 0.0))
            template_idx = [int(filter(lambda x: x.isdigit(), v)) for v in self.picked_lines]
            nstates = self.waveforms.shape[-1]
            pidx = int(nstates/3)
            if qq["mlseq"].shape[0] == self.waveforms.shape[0]:
                uidx, tidx = np.where(qq["mlseq"][:] == pidx)
            else:
                tidx, uidx = np.where(qq["mlseq"][:] == pidx)
            for (ii, tt) in enumerate(template_idx):
                cname = "cell%02d" % (ii+1, )
                cdir = os.path.join(os.path.dirname(self.sortfile), cname)
                if not os.path.isdir(cdir):
                    os.mkdir(cdir)
                iidx, = np.where(uidx == tt)
                timestamps = tidx[iidx]*1000/self.sampling_rate
                fname = cdir + os.path.sep + "spiketrain.mat"
                mio.savemat(fname, {"timestamps": timestamps,
                                    "spikeForm": self.waveforms[tt, :, :]})

            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText("Spiketrains saved")
            msg.setWindowTitle("Info")
            retval = msg.exec_()

    def select_waveforms(self, fname="spike_templates.hdf5"):
        if not os.path.isfile(fname):
            ff = os.path.join("hmmsort", fname)
            if os.path.isfile(ff):
                files = [ff]
            else:
                return
        else:
            files = [fname]
        if files:
            for f in files:
                dd = os.path.dirname(f)
                if not dd:
                    dd = "."
                self.basedir = dd
                self.sortfile = dd + os.path.sep + "hmmsort.mat"
                if not os.path.isfile(self.sortfile):
                    if "hmmsort" in self.basedir:
                        self.sortfile = os.path.join(dd, "..", "hmmsort.mat")
                if not os.path.isfile(self.sortfile):
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Critical)
                    msg.setText("Sort file " + self.sortfile + " not found")
                    msg.setWindowTitle("Error")
                with h5py.File(f, "r") as ff:
                    self.waveforms = ff["spikeForms"][:]
                    pp = ff["p"][:]
                    self.plot_waveforms(self.waveforms, pp)


def plot_waveforms(waveforms, pp):
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlabel("State")
    ax.set_ylabel("Amplitude")
    for i in xrange(waveforms.shape[0]):
        ax.plot(waveforms[i, 0, :], label="Waveform %d" % (i, ), picker=5)
    plt.legend()
    fig.canvas.mpl_connect('pick_event', pick_event)


def pick_event(event):
    artist = event.artist
    lw = artist.get_linewidth()
    label = artist.get_label()
    if lw == 1.5:
        artist.set_linewidth(2*lw)
        picked_lines.append(label)
    elif lw > 1.5:
        artist.set_linewidth(lw/2)
        picked_lines.remove(label)
    artist.figure.canvas.draw()


def select_waveforms(fname="spike_templates.hdf5"):
        files = glob.glob(fname)
        if files:
            for f in files:
                with h5py.File(f, "r") as ff:
                    waveforms = ff["spikeForms"][:]
                    pp = ff["p"][:]
                    plot_waveforms(waveforms, pp)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mw = ViewWidget()
    mw.select_waveforms()
    mw.show()
    sys.exit(app.exec_())
