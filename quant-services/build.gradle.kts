plugins {
    java
    id("org.springframework.boot") version "3.4.4" apply false
}

allprojects {
    group = "com.quant"
    version = "0.1.0"

    repositories {
        mavenCentral()
    }
}

subprojects {
    apply(plugin = "java")

    java {
        toolchain {
            languageVersion = JavaLanguageVersion.of(21)
        }
    }

    dependencies {
        "implementation"(platform("org.springframework.boot:spring-boot-dependencies:3.4.4"))
        "annotationProcessor"(platform("org.springframework.boot:spring-boot-dependencies:3.4.4"))
        "compileOnly"("org.projectlombok:lombok:1.18.34")
        "annotationProcessor"("org.projectlombok:lombok:1.18.34")
    }

    tasks.withType<JavaCompile> {
        options.encoding = "UTF-8"
    }
}
