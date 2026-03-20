(function () {
    var rootElement = document.getElementById("storefront-root");
    var dataElement = document.getElementById("storefront-data");

    if (!rootElement || !dataElement || !window.React || !window.ReactDOM || !window.htm) {
        return;
    }

    var html = window.htm.bind(window.React.createElement);
    var storefrontData = {};

    try {
        storefrontData = JSON.parse(dataElement.textContent || "{}");
    } catch (_error) {
        storefrontData = {};
    }

    var payload = storefrontData.payload || {};
    var routes = storefrontData.routes || {};
    var placeholderImage = (storefrontData.assets && storefrontData.assets.placeholder_image) || "";

    function formatPrice(value) {
        var amount = Number(value || 0);
        return "INR " + amount.toFixed(2);
    }

    function imageFallback(event) {
        if (!placeholderImage) {
            return;
        }
        var target = event && event.currentTarget;
        if (!target) {
            return;
        }
        target.onerror = null;
        target.src = placeholderImage;
    }

    function buildProductDetailUrl(productId) {
        return (routes.product_detail_template || "").replace("__PRODUCT_ID__", String(productId));
    }

    function buildCartAddUrl(productId) {
        return (routes.cart_add_template || "").replace("__PRODUCT_ID__", String(productId));
    }

    function ProductCard(props) {
        var product = props.product || {};

        return html`
            <article className="card">
                <img
                    src=${product.image_url || placeholderImage}
                    alt=${product.name || "Product"}
                    loading="lazy"
                    onError=${imageFallback}
                />
                <h3>${product.name || "Untitled Product"}</h3>
                <p>${product.brand || ""} | ${product.category || ""}</p>
                ${props.showStock ? html`<p>Stock: ${product.stock || 0}</p>` : null}
                <div className="row">
                    <strong>${formatPrice(product.price)}</strong>
                    <a href=${buildProductDetailUrl(product.id)}>View</a>
                </div>
            </article>
        `;
    }

    function HomeView() {
        var products = payload.products || [];

        return html`
            <div>
                <section className="hero">
                    <h1>Style Meets Intelligence</h1>
                    <p>Shop Max is now powered by a React JavaScript storefront for a smoother shopping flow.</p>
                    <a className="btn" href=${routes.products || "#"}>Explore Collection</a>
                </section>

                <section>
                    <h2>Featured Products</h2>
                    <div className="grid">
                        ${products.length
                            ? products.map(function (product) {
                                  return html`<${ProductCard} key=${product.id} product=${product} showStock=${false} />`;
                              })
                            : html`<p>No featured products available.</p>`}
                    </div>
                </section>
            </div>
        `;
    }

    function ProductsView() {
        var products = payload.products || [];
        var categories = payload.categories || [];
        var suggestions = payload.ai_suggestions || [];
        var filters = payload.filters || {};

        return html`
            <div>
                <h1>Products</h1>

                <section className="image-search-box">
                    <h2>Camera Image Search</h2>
                    <p className="muted">Take a photo or upload an image to find similar products.</p>
                    <form
                        method="post"
                        action=${routes.products_image_search || ""}
                        encType="multipart/form-data"
                        className="image-search-form"
                    >
                        <input type="file" name="search_image" accept="image/*" capture="environment" required />
                        <button className="btn" type="submit">Search by Image</button>
                    </form>
                </section>

                <form className="filters" method="get" action=${routes.products || ""}>
                    <input
                        type="text"
                        name="q"
                        placeholder="Search products or brands"
                        defaultValue=${filters.q || ""}
                    />
                    <select name="category" defaultValue=${filters.category || ""}>
                        <option value="">All Categories</option>
                        ${categories.map(function (categoryName) {
                            return html`<option key=${categoryName} value=${categoryName}>${categoryName}</option>`;
                        })}
                    </select>
                    <input
                        type="number"
                        name="min_price"
                        step="0.01"
                        placeholder="Min price"
                        defaultValue=${filters.min_price || ""}
                    />
                    <input
                        type="number"
                        name="max_price"
                        step="0.01"
                        placeholder="Max price"
                        defaultValue=${filters.max_price || ""}
                    />
                    <button className="btn" type="submit">Filter</button>
                </form>

                ${suggestions.length
                    ? html`
                          <section className="suggestions">
                              <div className="row">
                                  <h2>AI Suggestions From Your Visits</h2>
                              </div>
                              <div className="grid">
                                  ${suggestions.map(function (product) {
                                      return html`<${ProductCard}
                                          key=${"suggestion-" + product.id}
                                          product=${product}
                                          showStock=${true}
                                      />`;
                                  })}
                              </div>
                          </section>
                      `
                    : null}

                <div className="grid top-gap">
                    ${products.length
                        ? products.map(function (product) {
                              return html`<${ProductCard} key=${"product-" + product.id} product=${product} showStock=${true} />`;
                          })
                        : html`<p>No products found.</p>`}
                </div>
            </div>
        `;
    }

    function ProductDetailView() {
        var product = payload.product || null;
        var suggestions = payload.ai_suggestions || [];

        if (!product || !product.id) {
            return html`<p>Product not found.</p>`;
        }

        return html`
            <div>
                <section className="product-detail">
                    <img
                        id="product-img"
                        src=${product.image_url || placeholderImage}
                        alt=${product.name || "Product"}
                        loading="lazy"
                        onError=${imageFallback}
                    />
                    <div>
                        <h1>${product.name}</h1>
                        <p className="muted">${product.brand || ""} | ${product.category || ""}</p>
                        <p>${product.description || "No description available."}</p>
                        <h2>${formatPrice(product.price)}</h2>
                        <p>Available stock: ${product.stock || 0}</p>
                        <a className="btn" href=${buildCartAddUrl(product.id)}>Add to Cart</a>
                    </div>
                </section>

                ${suggestions.length
                    ? html`
                          <section className="suggestions top-gap">
                              <h2>AI Suggestions Based on Your Visits</h2>
                              <div className="grid">
                                  ${suggestions.map(function (item) {
                                      return html`<${ProductCard}
                                          key=${"detail-suggestion-" + item.id}
                                          product=${item}
                                          showStock=${false}
                                      />`;
                                  })}
                              </div>
                          </section>
                      `
                    : null}
            </div>
        `;
    }

    function StorefrontApp() {
        if (storefrontData.view === "products") {
            return html`<${ProductsView} />`;
        }
        if (storefrontData.view === "product_detail") {
            return html`<${ProductDetailView} />`;
        }
        return html`<${HomeView} />`;
    }

    if (typeof window.ReactDOM.createRoot === "function") {
        window.ReactDOM.createRoot(rootElement).render(html`<${StorefrontApp} />`);
        return;
    }

    window.ReactDOM.render(html`<${StorefrontApp} />`, rootElement);
})();
