const util = {
    createElement: function(name, attrs, innerHTML) {
        const elt = document.createElement(name);
        elt.innerHTML = innerHTML;
        for (const [key, value] of Object.entries(attrs)) {
            elt.setAttribute(key, value);
        }
        return elt;
    }
}