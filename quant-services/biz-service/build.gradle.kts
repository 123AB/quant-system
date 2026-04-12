plugins {
    id("org.springframework.boot")
}

dependencies {
    implementation(project(":quant-common"))
    implementation(project(":fund-module"))
    implementation(project(":soy-module"))
    implementation(project(":user-module"))
    implementation(project(":alert-module"))

    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    implementation("org.springframework.boot:spring-boot-starter-data-redis")
    implementation("org.springframework.boot:spring-boot-starter-actuator")

    runtimeOnly("org.postgresql:postgresql")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
}
