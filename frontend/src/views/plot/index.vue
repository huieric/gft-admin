<template>
  <div class="plot-page">
    <el-row :gutter="30" type="flex" justify="start" class="toolbar">
      <el-col :span="2">
        <el-select v-model="symbol" placeholder="Select Symbol" filterable>
          <el-option
            v-for="item in options.symbols"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
      </el-col>
      <el-col :span="2">
        <el-select v-model="interval" placeholder="Select Interval" filterable>
          <el-option
            v-for="item in options.intervals"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
      </el-col>
      <el-col :span="8">
        <el-select
          v-model="fields"
          multiple
          filterable
          clearable
          placeholder="Select Fields"
        >
          <el-option
            v-for="item in options.fields"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
      </el-col>
      <el-col :span="5">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          unlink-panels
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        />
      </el-col>
      <el-col :span="4">
        <el-select
          v-model="sources"
          multiple
          filterable
          clearable
          placeholder="Select Sources"
        >
          <el-option
            v-for="item in options.sources"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
      </el-col>
      <el-col :span="2">
        <el-button
          type="primary"
          @click="loadPlot"
          :loading="loading"
          style="width: 100%"
        >
          Plot
        </el-button>
      </el-col>
    </el-row>

    <div id="plot-div" class="plot-container"></div>

    <el-table :data="statsTableData" border max-height="250">
      <el-table-column prop="data" label="数据类型"></el-table-column>
      <el-table-column
        prop="count"
        label="数据点数量"
        sortable
        :formatter="formatNumber"
      ></el-table-column>
      <el-table-column
        prop="mean"
        label="平均值"
        sortable
        :formatter="formatNumber"
      ></el-table-column>
      <el-table-column
        prop="min"
        label="最小值"
        sortable
        :formatter="formatNumber"
      ></el-table-column>
      <el-table-column
        prop="max"
        label="最大值"
        sortable
        :formatter="formatNumber"
      ></el-table-column>
      <el-table-column
        prop="std"
        label="标准差"
        sortable
        :formatter="formatNumber"
      ></el-table-column>
      <el-table-column
        prop="correlation"
        label="相关系数"
        sortable
        :formatter="formatNumber"
      ></el-table-column>
    </el-table>
  </div>
</template>

<script>
import Plotly from "plotly.js-dist";

export default {
  name: "PlotPage",
  data() {
    return {
      symbol: "MNQ",
      interval: "1min",
      fields: ["volume"],
      sources: ["history", "running", "diff"],
      dateRange: [new Date("2025-07-14"), new Date()],
      loading: false,
      options: {
        symbols: [],
        intervals: [],
        fields: [],
        sources: ["history", "running", "diff"]
      },
      statsTableData: []
    };
  },
  mounted() {
    this.initOptions();
    this.loadPlot();
  },
  methods: {
    async initOptions() {
      const res = await fetch("/get-options");
      const data = await res.json();
      this.options.symbols = data.symbols;
      this.options.intervals = data.intervals;
      this.options.fields = data.fields;
    },
    async loadPlot() {
      this.loading = true;
      const payload = {
        symbol: this.symbol,
        interval: this.interval,
        fields: this.fields,
        start: this.dateRange[0]
          .toLocaleDateString("en-CA")
          .replace(/-/g, ""),
        end: this.dateRange[1].toLocaleDateString("en-CA").replace(/-/g, "")
      };
      const res = await fetch("/get-plot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      this.loading = false;
      if (data.series && data.series.length) {
        this.renderPlot(data);
        this.updateStats(data);
      }
    },
    renderPlot(data) {
      const colorPalette = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf"
      ];
      const fieldColorMap = {};
      this.fields.forEach((field, idx) => {
        fieldColorMap[field] = colorPalette[idx % colorPalette.length];
      });

      let traces = data.series
        .filter(s => this.sources.includes(s.label.split("_")[0]))
        .map(s => ({
          x: data.timestamps,
          y: s.values,
          mode: "lines",
          name: s.label,
          line: { color: fieldColorMap[s.label], width: 1.5 },
          hovertemplate: "%{x}<br>%{y}<extra>%{fullData.name}</extra>"
        }));

      let layout = {
        margin: { t: 20 },
        legend: { orientation: "h" },
        xaxis: { domain: [0, 1], title: "Time" },
        hovermode: "x unified"
      };

      if (this.sources.includes("diff")) {
        traces = traces.map(trace => ({
          ...trace,
          yaxis: trace.name.startsWith("diff_") ? "y2" : "y"
        }));
        layout = {
          ...layout,
          yaxis: { domain: [0.3, 1], title: "running/history" },
          yaxis2: { domain: [0, 0.25], title: "diff" }
        };
      }

      Plotly.newPlot("plot-div", traces, layout, { responsive: true });
    },
    updateStats(data) {
      this.statsTableData = [];
      for (const field of this.fields) {
        this.statsTableData.push(
          ...this.sources.map(name => {
            const item = data.stats[name] || {};
            return {
              data: `${name}_${field}`,
              count: item.count?.[field] ?? null,
              mean: item.mean?.[field] ?? null,
              min: item.min?.[field] ?? null,
              max: item.max?.[field] ?? null,
              std: item.std?.[field] ?? null,
              correlation:
                name === "history" || name === "running"
                  ? data.stats.corr?.[field] ?? null
                  : null
            };
          })
        );
      }
    },
    formatNumber(row, column, cellValue) {
      if (typeof cellValue === "number") {
        return cellValue.toFixed(4);
      }
      return cellValue;
    }
  }
};
</script>

<style scoped>
.plot-page {
  margin: auto;
  padding: 20px;
}
.plot-container {
  width: 100%;
  height: 800px;
}
.toolbar {
  margin-bottom: 20px;
}
</style>
