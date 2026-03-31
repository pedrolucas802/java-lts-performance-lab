package com.pedrolucas.lab.service;

import com.pedrolucas.lab.dto.ProductDTO;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.ws.rs.WebApplicationException;
import jakarta.ws.rs.core.Response;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@ApplicationScoped
public class DatabaseProductService {

    private static final int MAX_COUNT = 1000;
    private static final String PRODUCTS_SQL = """
            SELECT id, name, category, price, brand, region, segment, primary_tag, secondary_tag, tertiary_tag
            FROM benchmark_products
            ORDER BY id
            LIMIT ?
            """;

    @Inject
    BenchmarkDataSourceService dataSourceService;

    public List<ProductDTO> getProducts(int count) {
        int limit = Math.max(1, Math.min(count, MAX_COUNT));

        try (Connection connection = dataSourceService.getConnection();
             PreparedStatement statement = connection.prepareStatement(PRODUCTS_SQL)) {
            statement.setInt(1, limit);

            try (ResultSet resultSet = statement.executeQuery()) {
                List<ProductDTO> products = new ArrayList<>(limit);
                while (resultSet.next()) {
                    products.add(mapProduct(resultSet));
                }
                return products;
            }
        } catch (SQLException e) {
            throw new WebApplicationException(
                    "Failed to load DB-backed products.",
                    e,
                    Response.Status.INTERNAL_SERVER_ERROR
            );
        }
    }

    private ProductDTO mapProduct(ResultSet resultSet) throws SQLException {
        Map<String, String> attributes = new LinkedHashMap<>();
        attributes.put("brand", resultSet.getString("brand"));
        attributes.put("region", resultSet.getString("region"));
        attributes.put("segment", resultSet.getString("segment"));

        List<String> tags = List.of(
                resultSet.getString("primary_tag"),
                resultSet.getString("secondary_tag"),
                resultSet.getString("tertiary_tag")
        );

        return new ProductDTO(
                resultSet.getLong("id"),
                resultSet.getString("name"),
                resultSet.getString("category"),
                resultSet.getDouble("price"),
                tags,
                attributes
        );
    }
}
