# syntax=docker/dockerfile:1
# Full-stack "Greedy Cars" (ingSoftII / SCRUM / integrador) host image for the
# SCL network-topology plugin.
#
# A host of type `greedy-server` (see HOST_TYPES in app.py) runs the entire app:
# a MariaDB database (:3306), the greedy_cars Spring Boot API (:9000), the
# greedy_institucional site (:8080), the gredy_cars_client app (:8081), and an
# nginx front door on :80 reverse-proxying the three context paths so the whole
# app is reachable same-origin from any host in the topology.
#
# The repo (ingSoftII) is cloned at BUILD time by the Docker daemon (host
# egress) using a SPARSE checkout — only SCRUM/integrador is materialised, so
# the 57k-file monorepo isn't pulled whole. The third-party code is never
# vendored into this plugin's git tree (see .gitignore).

ARG GREEDY_HOST_URL=https://github.com/r-baggioII/ingSoftII
ARG GREEDY_HOST_REF=9cab62a633d4ba23135a8febbb743088183896f6

FROM scl-plugin-network-topology-ubuntu:0.1

ARG GREEDY_HOST_URL
ARG GREEDY_HOST_REF
LABEL org.opencontainers.image.source="${GREEDY_HOST_URL}" \
      org.opencontainers.image.revision="${GREEDY_HOST_REF}"
ENV DEBIAN_FRONTEND=noninteractive

# ── System deps: git (clone), MariaDB (DB), nginx (front door), JDK 21 + Maven
#    (build the Spring Boot WARs at image-build time), curl/ca-certs ──────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        mariadb-server \
        mariadb-client \
        nginx \
        openjdk-21-jdk \
        maven \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && java -version && mvn -v

# ── Sparse-clone ONLY SCRUM/integrador out of the ingSoftII monorepo ─────────
#    (full clone is ~57k files; we need just this subdir.) Drop .git afterwards.
RUN mkdir -p /srv /tmp/ingsoft \
    && git -C /tmp/ingsoft init \
    && git -C /tmp/ingsoft remote add origin "${GREEDY_HOST_URL}" \
    && git -C /tmp/ingsoft sparse-checkout init --no-cone \
    && git -C /tmp/ingsoft sparse-checkout set SCRUM/integrador \
    && git -C /tmp/ingsoft fetch --depth 1 origin "${GREEDY_HOST_REF}" \
    && git -C /tmp/ingsoft checkout --detach FETCH_HEAD \
    && test "$(git -C /tmp/ingsoft rev-parse HEAD)" = "${GREEDY_HOST_REF}" \
    && cd /tmp/ingsoft \
    && cp -a /tmp/ingsoft/SCRUM/integrador /srv/repo \
    && rm -rf /tmp/ingsoft

# ── Patch Auth0 bootstrap. The API does not use Spring's OAuth2 login client,
#    so disable that eager auto-configuration. Keep resource-server JWT support,
#    but derive the lazy JWKS endpoint from the configured issuer instead of
#    baking a tenant into the image.
RUN sed -i '/^spring\.security\.oauth2\.client\./s/^/#AUTH0-DISABLED# /' \
        /srv/repo/greedy_cars/src/main/resources/application.properties \
    && sed -i 's#NimbusJwtDecoder jwtDecoder = JwtDecoders\.fromIssuerLocation(issuerUri);#NimbusJwtDecoder jwtDecoder = NimbusJwtDecoder.withJwkSetUri(issuerUri.replaceAll("/+$", "") + "/.well-known/jwks.json").build();#' \
        /srv/repo/greedy_cars/src/main/java/com/uncuyo/greedy_cars/config/SecurityConfig.java \
    && test "$(grep -c 'AUTH0-DISABLED' /srv/repo/greedy_cars/src/main/resources/application.properties)" -ge 2 \
    && ! grep -q '^spring\.security\.oauth2\.client\.' /srv/repo/greedy_cars/src/main/resources/application.properties \
    && grep -q 'issuerUri.replaceAll' /srv/repo/greedy_cars/src/main/java/com/uncuyo/greedy_cars/config/SecurityConfig.java

# The upstream client currently contains two component-scanned copies of three
# Auth0 controllers with identical default bean names. The template copies are
# stale and prevent the whole client WAR from starting.
RUN rm -f \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/template/controller/Auth0CallbackController.java \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/template/controller/Auth0Controller.java \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/template/controller/Auth0ViewController.java \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/template/service/Auth0Service.java \
    && test -f /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller/Auth0CallbackController.java \
    && test -f /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller/Auth0Controller.java \
    && test -f /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller/Auth0ViewController.java \
    && test -f /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/service/Auth0Service.java

# Make Auth0 redirects, the callback-to-API request, and CORS use the topology's
# configured internal origin. Spring maps GREEDY_PUBLIC_BASE_URL to this
# property, so no public host or fixed topology address is compiled into Java.
RUN for file in \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller/Auth0ViewController.java \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller/Auth0CallbackController.java; do \
      sed -i 's#    private String contextPath;#    private String contextPath;\n\n    @Value("${greedy.public-base-url}")\n    private String publicBaseUrl;#' "$file"; \
    done \
    && sed -i \
      's#"http://161\.153\.217\.110:18082" + contextPath#publicBaseUrl + contextPath#' \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller/Auth0ViewController.java \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller/Auth0CallbackController.java \
    && sed -i \
      's#"http://161\.153\.217\.110:18082/greedy_cars/api/auth0/post-login"#publicBaseUrl + "/greedy_cars/api/auth0/post-login"#' \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller/Auth0CallbackController.java \
    && sed -i 's#    private String audience;#    private String audience;\n\n    @Value("${greedy.public-base-url}")\n    private String publicBaseUrl;#' \
      /srv/repo/greedy_cars/src/main/java/com/uncuyo/greedy_cars/config/SecurityConfig.java \
    && sed -i 's#"http://161\.153\.217\.110:18082"#publicBaseUrl#' \
      /srv/repo/greedy_cars/src/main/java/com/uncuyo/greedy_cars/config/SecurityConfig.java \
    && ! grep -R -q '161\.153\.217\.110:18082' \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller \
      /srv/repo/greedy_cars/src/main/java/com/uncuyo/greedy_cars/config/SecurityConfig.java

# Encode the scope query parameter emitted by the server-side login redirect.
RUN sed -i 's#scope=openid profile email#scope=openid%%20profile%%20email#' \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller/Auth0ViewController.java \
    && grep -q 'scope=openid%%20profile%%20email' \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/java/com/gredy_cars_client/gredy_cars_client/shared/controller/Auth0ViewController.java

# Remove live credentials and old public URLs inherited from the upstream
# properties. Runtime values arrive through the protected topology env file.
RUN sed -i \
      -e 's#^app\.jwt\.secret=.*#app.jwt.secret=not-configured#' \
      -e 's#^mercadopago\.access-token=.*#mercadopago.access-token=not-configured#' \
      -e 's#^mercadopago\.frontend-url-success=.*#mercadopago.frontend-url-success=not-configured#' \
      -e 's#^mercadopago\.frontend-url-failure=.*#mercadopago.frontend-url-failure=not-configured#' \
      -e 's#^mercadopago\.frontend-url-pending=.*#mercadopago.frontend-url-pending=not-configured#' \
      -e 's#^mercadopago\.back-url-success=.*#mercadopago.back-url-success=not-configured#' \
      -e 's#^mercadopago\.back-url-failure=.*#mercadopago.back-url-failure=not-configured#' \
      -e 's#^mercadopago\.back-url-pending=.*#mercadopago.back-url-pending=not-configured#' \
      -e 's#^spring\.mail\.username=.*#spring.mail.username=not-configured#' \
      -e 's#^spring\.mail\.password=.*#spring.mail.password=not-configured#' \
      -e 's#^spring\.security\.oauth2\.resourceserver\.jwt\.issuer-uri=.*#spring.security.oauth2.resourceserver.jwt.issuer-uri=https://not-configured.invalid/#' \
      -e 's#client-id=.*#client-id=not-configured#' \
      -e 's#client-secret=.*#client-secret=not-configured#' \
      -e 's|^#AUTH0-DISABLED# spring\.security\.oauth2\.client\.provider\.auth0\.issuer-uri=.*|#AUTH0-DISABLED# spring.security.oauth2.client.provider.auth0.issuer-uri=https://not-configured.invalid/|' \
      -e '/^auth0\.audience=/a greedy.public-base-url=http://10.77.2.12' \
      /srv/repo/greedy_cars/src/main/resources/application.properties \
    && sed -i \
      -e 's#^greedy\.api\.base-url=.*#greedy.api.base-url=http://localhost:9000/greedy_cars/api#' \
      -e 's#^auth0\.domain=.*#auth0.domain=not-configured.invalid#' \
      -e 's#^auth0\.clientId=.*#auth0.clientId=not-configured#' \
      -e 's#^auth0\.clientSecret=.*#auth0.clientSecret=not-configured#' \
      -e '/^auth0\.audience=/a greedy.public-base-url=http://10.77.2.12' \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/resources/application.properties \
    && sed -i -E \
      's/^(MYSQL_ROOT_PASSWORD|MYSQL_PASSWORD|JWT_SECRET|MERCADOPAGO_ACCESS_TOKEN|SPRING_MAIL_USERNAME|SPRING_MAIL_PASSWORD|GREEDY_API_PASSWORD)=.*/\1=not-configured/' \
      /srv/repo/.env.example \
    && grep -RIl --exclude-dir=target '161\.153\.217\.110:18082' /srv/repo \
      | xargs -r sed -i 's#161\.153\.217\.110:18082#10.77.2.12#g' \
    && ! grep -R -qE 'APP_USR-|ngrok-free|greedyteam0@gmail|161\.153\.217\.110:18082' \
      /srv/repo/.env.example \
      /srv/repo/greedy_cars/src/main/resources/application.properties \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/resources/application.properties \
    && ! grep -R -q '161\.153\.217\.110:18082' /srv/repo

# Thymeleaf's strict parser rejects the duplicate href attribute in the client
# landing page, causing the otherwise-running UI to return HTTP 500.
RUN sed -i 's/aria-expanded="false" href="#">Pages/aria-expanded="false">Pages/' \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/resources/templates/index.html \
    && ! grep -q 'aria-expanded="false" href="#">Pages' \
      /srv/repo/gredy_cars_client/gredy_cars_client/src/main/resources/templates/index.html

# ── Build the three Spring Boot WARs to FIXED names. Each pom sets an explicit
#    <finalName>, so `mvn package` emits target/<finalName>.war (no version
#    suffix): greedy_cars.war, greedy_institucional.war, gredy_cars_client.war.
#    greedy_cars first (institucional + client depend on it at runtime only). ──
RUN mkdir -p /srv/wars \
    && cd /srv/repo/greedy_cars \
    && mvn -q -B -DskipTests clean package \
    && cp target/greedy_cars.war /srv/wars/greedy_cars.war \
    && cd /srv/repo/greedy_institucional \
    && mvn -q -B -DskipTests clean package \
    && cp target/greedy_institucional.war /srv/wars/greedy_institucional.war \
    && cd /srv/repo/gredy_cars_client/gredy_cars_client \
    && mvn -q -B -DskipTests clean package \
    && cp target/gredy_cars_client.war /srv/wars/gredy_cars_client.war \
    && ls -lh /srv/wars

# ── MariaDB: bind on all interfaces + skip-name-resolve so TCP clients match
#    the 'greedy_cars'@'127.0.0.1'/'%' accounts (mirrors scl-repo-host). ────────
RUN printf '[mysqld]\nbind-address = 0.0.0.0\nskip-name-resolve = 1\n' > /etc/mysql/mariadb.conf.d/99-greedy-bind.cnf

# ── nginx front door: / → client app, /greedy_cars/ → API, etc. ──────────────
COPY nginx-greedy.conf /etc/nginx/sites-available/greedy
RUN rm -f /etc/nginx/sites-enabled/default \
    && ln -sf /etc/nginx/sites-available/greedy /etc/nginx/sites-enabled/greedy

# ── Supervisor: MariaDB -> 3 Spring Boot apps -> nginx ───────────────────────
COPY greedy-app-start.sh /usr/local/bin/greedy-app-start.sh
COPY greedy-healthcheck.sh /usr/local/bin/greedy-healthcheck.sh
COPY greedy-seed.sql /usr/local/share/greedy-seed.sql
RUN chmod +x /usr/local/bin/greedy-app-start.sh /usr/local/bin/greedy-healthcheck.sh

EXPOSE 80 3306 9000 8080 8081
HEALTHCHECK --interval=10s --timeout=5s --start-period=180s --retries=12 \
    CMD ["/usr/local/bin/greedy-healthcheck.sh"]
WORKDIR /srv/repo

