package com.pedrolucas.lab.api;

import com.pedrolucas.lab.dto.AggregateResponse;
import com.pedrolucas.lab.service.AggregateService;
import jakarta.inject.Inject;
import jakarta.ws.rs.DefaultValue;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;

@Path("/aggregate")
@Produces(MediaType.APPLICATION_JSON)
public class AggregateResource {

    @Inject
    AggregateService aggregateService;

    @GET
    public AggregateResponse aggregate(
            @QueryParam("mode") @DefaultValue("platform") String mode
    ) {
        if ("virtual".equalsIgnoreCase(mode)) {
            return aggregateService.runVirtualTasks();
        }

        return aggregateService.runPlatformTasks();
    }
}