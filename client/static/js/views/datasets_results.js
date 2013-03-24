PANDA.views.DatasetsResults = Backbone.View.extend({
    search: null,

    initialize: function(options) {
        _.bindAll(this);
    },

    reset: function(search) {
        this.search = search;
    },

    render: function() {
        var context = PANDA.utils.make_context(this.search.datasets.meta);

        context["query"] = this.search.query;
        context["category"] = this.search.category;
        context["datasets"] = this.search.datasets.results()["datasets"];
        context["pager_unit"] = "dataset";
        context["row_count"] = this.search.datasets.meta.total_count;
        context["root_url"] = "#datasets/" + this.search.category + "/" + (this.search.query || "*");

        context["pager"] = PANDA.templates.inline_pager(context);

        this.$el.html(PANDA.templates.datasets_results(context));

        // Enable result sorting
        $("#datasets-results table").tablesorter({
            cssHeader: "no-sort-header",
            cssDesc: "sort-desc-header",
            cssAsc: "sort-asc-header",
            headers: {
                0: { sorter: "text" },
                1: { sorter: false },
                2: { sorter: "text" },
                3: { sorter: false }
            },
            textExtraction: function(node) {
                return $(node).children(".sort-value").text();
            }
        });
    }
});

