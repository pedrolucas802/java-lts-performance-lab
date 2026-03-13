package com.pedrolucas.lab.api;

import com.pedrolucas.lab.dto.TransformRequest;
import com.pedrolucas.lab.dto.TransformResponse;
import com.pedrolucas.lab.service.TransformService;
import jakarta.inject.Inject;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

@Path("/transform")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class TransformResource {

    @Inject
    TransformService transformService;

    @POST
    public TransformResponse transform(TransformRequest request) {
        return transformService.transform(request);
    }
}