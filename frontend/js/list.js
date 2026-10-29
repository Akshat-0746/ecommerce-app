const grid = document.getElementById("product-grid");
const statusEl = document.getElementById("status");
const form = document.getElementById("filter-form");
const searchInput = document.getElementById("search");
const categorySelect = document.getElementById("category");
const minPriceInput = document.getElementById("min-price");
const maxPriceInput = document.getElementById("max-price");
const DEBOUNCE_DELAY = 300;

function getFilterParams() {
    const params = new URLSearchParams();
    const search = searchInput.value.trim();
    const category = categorySelect.value.trim();
    const minPrice = minPriceInput.value.trim();
    const maxPrice = maxPriceInput.value.trim();

    if (search) params.set("search", search);
    if (category) params.set("category", category);
    if (minPrice) params.set("min_price", minPrice);
    if (maxPrice) params.set("max_price", maxPrice);

    return params;
}

function buildCard(product) {
    const card = document.createElement("a");
    card.className = "card";
    card.href = `products.html?id=${product.id}`;

    const img = document.createElement("img");
    img.src = product.image_url;
    img.alt = product.name;
    img.loading = "lazy";

    const body = document.createElement("div");
    body.className = "card-body";

    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = product.category;

    const title = document.createElement("h2");
    title.textContent = product.name;

    const description = document.createElement("p");
    description.className = "description";
    description.textContent = product.description;

    const price = document.createElement("p");
    price.className = "price";
    price.textContent = formatPrice(product.price);

    body.append(badge, title, description, price);
    card.append(img, body);
    return card;
}

async function loadProducts() {
    statusEl.textContent = "Loading...";

    try {
        const params = getFilterParams();
        const data = await fetchJSON(`/api/products?${params}`);
        grid.textContent = "";
        for (const product of data.products) {
            grid.appendChild(buildCard(product));
        }
        statusEl.textContent =
            data.count === 0
                ? "No products match your filters."
                : `${data.count} product(s) found`;
    } catch (error) {
        grid.replaceChildren();
        statusEl.textContent = `Error: ${error.message}`;
    }
}

async function loadCategories() {
    try {
        const categories = await fetchJSON("/api/categories");
        for (const name of categories) {
            const option = document.createElement("option");
            option.value = name;
            option.textContent = name;
            categorySelect.appendChild(option);
        }
    } catch (error) {
        console.error("Could not load categories:", error);
    }
}

form.addEventListener("submit", (event) => {
    event.preventDefault();
    loadProducts();
});

form.addEventListener("reset", () => setTimeout(loadProducts, 0));
categorySelect.addEventListener("change", loadProducts);

let debounceTimer;
searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(loadProducts, DEBOUNCE_DELAY);
});

loadCategories();
loadProducts();