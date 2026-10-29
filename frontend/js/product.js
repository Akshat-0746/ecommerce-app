const statusEl = document.getElementById("status");
const detailEl = document.getElementById("product-detail");

function buildDetail(product) {
    const wrapper = document.createElement("div");
    wrapper.className = "detail";

    const img = document.createElement("img");
    img.src = product.image_url;
    img.alt = product.name;

    const info = document.createElement("div");
    info.className = "detail-info";

    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = product.category;

    const title = document.createElement("h1");
    title.textContent = product.name;

    const price = document.createElement("p");
    price.className = "price";
    price.textContent = formatPrice(product.price);

    const desc = document.createElement("p");
    desc.textContent = product.description;

    const stock = document.createElement("p");
    stock.className = product.stock > 0 ? "in-stock" : "out-of-stock";
    stock.textContent =
        product.stock > 0 ? `In stock (${product.stock} available)` : "Out of stock";

    info.append(badge, title, price, desc, stock);
    wrapper.append(img, info);
    return wrapper;
}

async function loadProduct() {
    // The URL looks like products.html?id=3 - read the "id" part
    const id = new URLSearchParams(window.location.search).get("id");
    if (!id) {
        statusEl.textContent = "No product selected.";
        return;
    }

    statusEl.textContent = "Loading...";
    try {
        const product = await fetchJSON(`/api/products/${encodeURIComponent(id)}`);
        document.title = `${product.name} - ShopEasy`;
        detailEl.appendChild(buildDetail(product));
        statusEl.textContent = "";
    } catch (err) {
        statusEl.textContent = `Error: ${err.message}`;
    }
}

loadProduct();