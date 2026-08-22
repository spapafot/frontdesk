import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MessageBubble } from "./MessageBubble";

describe("MessageBubble product results", () => {
  it("renders safe read-only product cards", () => {
    render(
      <MessageBubble
        showDebug={false}
        message={{
          id: "assistant-1",
          role: "assistant",
          content: "I found 1 matching product.",
          sources: [],
          toolCalls: [],
          productResults: {
            page: 1,
            has_more: true,
            products: [
              {
                id: 21,
                name: "Blue Dress",
                slug: "blue-dress",
                summary: "",
                price: "25.99",
                regular_price: "29.99",
                sale_price: "25.99",
                currency_code: "EUR",
                currency_symbol: "€",
                on_sale: true,
                is_in_stock: true,
                has_options: true,
                image_url: "https://cdn.example/blue.jpg",
                product_url: "https://shop.example/product/blue-dress/",
                attributes: [
                  {
                    name: "Size",
                    taxonomy: "pa_size",
                    terms: [{ name: "Medium", slug: "medium" }],
                  },
                ],
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByRole("region", { name: "Product results" })).toHaveTextContent(
      "Blue Dress",
    );
    expect(screen.getByText("Size: Medium")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View product" })).toHaveAttribute(
      "href",
      "https://shop.example/product/blue-dress/",
    );
    expect(screen.getByText(/show me more/i)).toBeInTheDocument();
  });
});
