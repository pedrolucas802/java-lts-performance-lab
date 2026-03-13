package com.pedrolucas.lab.api;

import com.pedrolucas.lab.dto.ProductDTO;
import com.pedrolucas.lab.service.ProductService;
import jakarta.inject.Inject;
import jakarta.ws.rs.DefaultValue;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;

import java.util.List;

@Path("/products")
@Produces(MediaType.APPLICATION_JSON)
public class ProductResource {

    @Inject
    ProductService productService;

    @GET
    public List<ProductDTO> getProducts(@QueryParam("count") @DefaultValue("100") int count) {
        return productService.getProducts(count);
    }
}