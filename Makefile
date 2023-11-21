SRC = $(shell find bleMD)

bleMD.zip: $(SRC)
	zip -r bleMD.zip bleMD/*

