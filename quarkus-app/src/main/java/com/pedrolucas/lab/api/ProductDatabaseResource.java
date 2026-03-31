package com.pedrolucas.lab.api;

import com.pedrolucas.lab.dto.ProductDTO;
import com.pedrolucas.lab.service.DatabaseProductService;
import jakarta.inject.Inject;
import jakarta.ws.rs.DefaultValue;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;

import java.util.List;

@Path("/products-db")
@Produces(MediaType.APPLICATION_JSON)
public class ProductDatabaseResource {

    @Inject
    DatabaseProductService databaseProductService;

    @GET
    public List<ProductDTO> getProducts(@QueryParam("count") @DefaultValue("500") int count) {
        return databaseProductService.getProducts(count);
    }
}
