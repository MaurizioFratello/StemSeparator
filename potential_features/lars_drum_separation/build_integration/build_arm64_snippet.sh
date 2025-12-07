# Build LARS Service binary (AUTOMATIC SETUP)
echo ""
echo -e "${BLUE}Building LARS Service binary...${NC}"
LARS_DIR="packaging/lars_service"

if [ ! -d "$LARS_DIR" ]; then
    echo -e "${YELLOW}WARNING: LARS service directory not found${NC}"
    echo -e "${YELLOW}LARS drum separation will not be available${NC}"
else
    cd "$LARS_DIR"

    # Setup conda for bash
    eval "$(conda shell.bash hook)"

    # Check if lars-env exists, create if not
    LARS_ENV_NAME="lars-env"
    if ! conda env list | grep -q "^${LARS_ENV_NAME} "; then
        echo -e "${YELLOW}LARS environment not found. Creating automatically...${NC}"
        # Python 3.10 recommended for LarsNet
        conda create -n "$LARS_ENV_NAME" python=3.10 -y
        if [ $? -ne 0 ]; then
            echo -e "${RED}WARNING: Failed to create lars-env${NC}"
            echo -e "${YELLOW}Continuing without LARS service${NC}"
            conda deactivate
            cd - > /dev/null
        else
            echo -e "${GREEN}✓ Created lars-env (Python 3.10)${NC}"
        fi
    fi

    # Build binary (if environment was created/exists)
    if conda env list | grep -q "^${LARS_ENV_NAME} "; then
        echo -e "${BLUE}Building LARS binary...${NC}"
        if [ -f "build.sh" ]; then
            # Build with output visible for debugging
            ./build.sh
            BUILD_STATUS=$?

            if [ $BUILD_STATUS -eq 0 ]; then
                LARS_BINARY="dist/lars-service"
                if [ -f "$LARS_BINARY" ]; then
                    chmod +x "$LARS_BINARY" 2>/dev/null || true
                    if [ -x "$LARS_BINARY" ]; then
                        LARS_SIZE=$(du -h "$LARS_BINARY" | cut -f1)
                        echo -e "${GREEN}✓ LARS service built successfully${NC}"
                        echo -e "${BLUE}  Binary: $LARS_BINARY ($LARS_SIZE)${NC}"
                    else
                        echo -e "${YELLOW}WARNING: LARS binary exists but is not executable${NC}"
                    fi
                else
                    echo -e "${YELLOW}WARNING: LARS service build completed but binary not found${NC}"
                fi
            else
                echo -e "${YELLOW}WARNING: LARS service build failed${NC}"
                echo -e "${YELLOW}Continuing without LARS service${NC}"
            fi
        else
            echo -e "${YELLOW}WARNING: build.sh not found in lars_service${NC}"
        fi

        # Deactivate lars-env
        conda deactivate
    fi

    cd - > /dev/null
fi
