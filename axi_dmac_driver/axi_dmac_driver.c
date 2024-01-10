/*
 * ADI AXI DMAC IIO Client Module
 *
 * Copyright 2023 30N6
 *
 * Licensed under the GPL-2.
 *
 * Inspired by ad_adc.c
 *
 */

#include <linux/module.h>
#include <linux/io.h>
#include <linux/dma-mapping.h>
#include <linux/dmaengine.h>
#include <linux/platform_device.h>
#include <linux/of.h>

#include <linux/iio/iio.h>
#include <linux/iio/sysfs.h>
#include <linux/iio/buffer.h>
#include <linux/iio/buffer_impl.h>
#include <linux/iio/buffer-dma.h>
#include <linux/iio/buffer-dmaengine.h>

static int dma_hw_submit_block(struct iio_dma_buffer_queue *queue, struct iio_dma_buffer_block *block)
{
	struct iio_dev *indio_dev = queue->driver_data;
	int direction = DMA_TO_DEVICE;

	if (indio_dev->direction == IIO_DEVICE_DIRECTION_IN) 
	{
		direction               = DMA_FROM_DEVICE;
		block->block.bytes_used = block->block.size;
	}

	return iio_dmaengine_buffer_submit_block(queue, block, direction);
}

static const struct iio_dma_buffer_ops dma_buffer_ops = 
{
	.submit = dma_hw_submit_block,
	.abort  = iio_dmaengine_buffer_abort,
};

int dma_configure_ring_stream(struct iio_dev *indio_dev, const char *dma_name)
{
	struct iio_buffer *buffer;

	if (dma_name == NULL)
		dma_name = "d2h";

	buffer = devm_iio_dmaengine_buffer_alloc(indio_dev->dev.parent, dma_name,
			&dma_buffer_ops, indio_dev);

	if (IS_ERR(buffer))
		return PTR_ERR(buffer);

	indio_dev->modes |= INDIO_BUFFER_HARDWARE;
	iio_device_attach_buffer(indio_dev, buffer);

	return 0;
}

struct dma_info 
{
	unsigned int                direction;
	const struct iio_chan_spec* channels;
	unsigned int                num_channels;
};

#define IIO_CHANNEL(_chan, _rb, _direction) { \
	.type       = IIO_VOLTAGE, \
	.indexed    = 1, \
	.channel    = _chan, \
	.modified   = 0, \
	.channel2   = 0, \
	.output     = _direction, \
	.address    = _chan, \
	.scan_index = _chan, \
	.scan_type = { \
		.sign         = 'u', \
		.realbits     = _rb, \
		.storagebits  = _rb, \
		.shift        = 0, \
		.endianness   = IIO_LE, \
	}, \
}

#define AXI_DMAC_MAX_CHANNEL 1

struct dma_state 
{
	struct    iio_info      iio_info;
	unsigned  id;
	struct    iio_chan_spec	channels[AXI_DMAC_MAX_CHANNEL];
};

static const struct iio_chan_spec iio_channels_d2h[] = 
{
	IIO_CHANNEL(0, 32, IIO_DEVICE_DIRECTION_IN),
};

static const struct dma_info dma_d2h_info = 
{
	.direction    = IIO_DEVICE_DIRECTION_IN,
	.channels     = iio_channels_d2h,
	.num_channels = ARRAY_SIZE(iio_channels_d2h),
};

static const struct iio_chan_spec iio_channels_h2d[] = 
{
	IIO_CHANNEL(0, 32, IIO_DEVICE_DIRECTION_OUT),
};

static const struct dma_info dma_h2d_info = {
	.direction    = IIO_DEVICE_DIRECTION_OUT,
	.channels     = iio_channels_h2d,
	.num_channels = ARRAY_SIZE(iio_channels_h2d),
};

static const struct iio_info dmac_info = {
};

static const struct of_device_id dma_of_match[] = {
	{ .compatible = "adi,iio-dma-d2h-1.00.a", .data = &dma_d2h_info },
	{ .compatible = "adi,iio-dma-h2d-1.00.a", .data = &dma_h2d_info },
	{ /* end of list */ },
};
MODULE_DEVICE_TABLE(of, dma_of_match);

static int dma_probe(struct platform_device *pdev)
{
	const struct dma_info*      info;
	const struct of_device_id*  id;
	struct device_node*         np = pdev->dev.of_node;

	const char*       dma_name;
	struct iio_dev*   indio_dev;
	struct dma_state* st;
	struct resource*  mem;
	int               ret;

	id = of_match_node(dma_of_match, np);
	if (!id)
		return -ENODEV;

	info = id->data;
	indio_dev = devm_iio_device_alloc(&pdev->dev, sizeof(*st));
	if (indio_dev == NULL)
	{
	  dev_info(&pdev->dev, "%s: Device alloc failed.", __func__);
		return -ENOMEM;
	}

	st = iio_priv(indio_dev);
	mem = platform_get_resource(pdev, IORESOURCE_MEM, 0); //TODO: do something with mem?

	platform_set_drvdata(pdev, indio_dev);

	indio_dev->dev.parent   = &pdev->dev;
	indio_dev->name         = np->name;
	indio_dev->modes        = INDIO_DIRECT_MODE;
	indio_dev->info         = &dmac_info;
	indio_dev->channels     = info->channels;
	indio_dev->num_channels = info->num_channels;
	indio_dev->direction    = info->direction;

	if (of_property_read_string_index(np, "dma-names", 0, &dma_name))
	{
	  dev_info(&pdev->dev, "%s: Failed to read dma-names.", __func__);
		return -ENODEV;
	}

	ret = dma_configure_ring_stream(indio_dev, dma_name);
	if (ret)
	{
	  dev_info(&pdev->dev, "%s: Failed to configure ring stream.", __func__);
		return ret;
	}

	ret = devm_iio_device_register(&pdev->dev, indio_dev);
	if (ret)
	{
	  dev_info(&pdev->dev, "%s : Failed to register IIO device", __func__);
		return ret;
	}

	dev_info(&pdev->dev, "%s : Found", __func__);
	return 0;
}

static struct platform_driver dma_driver = {
	.driver = {
		.name           = KBUILD_MODNAME,
		.owner          = THIS_MODULE,
		.of_match_table = dma_of_match,
	},
	.probe = dma_probe
};

module_platform_driver(dma_driver);

MODULE_AUTHOR("30N6");
MODULE_DESCRIPTION("ADI AXI DMAC IIO client driver");
MODULE_LICENSE("GPL v2");

